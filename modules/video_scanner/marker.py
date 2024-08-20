import os
import typing
import functools
import glob
import logging
from dataclasses import dataclass, field

import numpy as np
import cv2 as cv

from . import utils
from modules import debug_flags

log = logging.getLogger(__name__)
MarkerName = typing.NewType('MarkerName', str)

MARKER_FOLDER = os.path.join('assets', 'detection')
DETECTION_AUTO_THRESHOLD = object()

@dataclass(slots=True)
class Marker():
  name : MarkerName
  data : np.ndarray = field(repr=False)

  channel_count : int = field(init=False)
  width: int = field(init=False)
  height: int = field(init=False)

  alpha_channel : np.ndarray = field(init=False, repr=False)
  color_channel : np.ndarray = field(init=False, repr=False)

  def split_alpha_channel(self):
    marker_channels = cv.split(self.data)
    self.alpha_channel = None
    if len(marker_channels) > 3:
      self.alpha_channel = marker_channels[3]
      unique_alpha = np.unique(self.alpha_channel)

    # remove alpha channel if only contains all opaque
    if self.alpha_channel is not None and unique_alpha.min() == 255 and unique_alpha.max() == 255:
      self.alpha_channel = None

    self.color_channel = cv.merge(marker_channels[:3])

  def analyze_dimensions(self):
    if not hasattr(self, 'color_channel') or self.color_channel is None:
      self.split_alpha_channel()

    if self.color_channel.ndim > 2:
      self.channel_count, self.width, self.height = self.color_channel.shape[::-1]
    else:
      self.channel_count, self.width, self.height = 1, *self.color_channel.shape[::-1]

@dataclass(slots=True)
class MarkerResult():
  marker : Marker
  ok : bool
  coords : np.ndarray = field(init=False, default=None, repr=False)

  def __bool__(self) -> bool:
    return self.ok

def load_markers(root_dir = MARKER_FOLDER) -> dict[MarkerName, Marker]:
  '''
  Load detection markers.
  '''
  image_map = dict()
  for fn in glob.iglob('*.png', root_dir = root_dir):
    name, ext = os.path.splitext(fn)
    img = cv.imread(os.path.join(root_dir, fn), cv.IMREAD_UNCHANGED)

    marker = Marker(name, img)
    marker.split_alpha_channel()
    marker.analyze_dimensions()

    image_map[name] = marker

  return image_map

def detect_frame_with_marker(
  frame, marker : Marker, *,
  single_color_mode : bool = False,
  template_mode : int = cv.TM_CCOEFF_NORMED,
  detection_threshold : float | object = DETECTION_AUTO_THRESHOLD,
  detection_region : tuple[slice, slice] = None,
) -> MarkerResult:
  '''
  Marker detection on an image.
  '''
  if isinstance(detection_region, tuple):
    detection_region = utils.slice_to_pixels(frame, detection_region)

    frame = frame[
      detection_region[1].start:detection_region[1].stop,
      detection_region[0].start:detection_region[0].stop,
    ]
  else:
    detection_region = (slice(0, None), slice(0, None))

  if detection_threshold is DETECTION_AUTO_THRESHOLD:
    detection_threshold = utils.calculate_detection_threshold(frame, marker)

  if single_color_mode:
    # single color focuses on grayscale
    gray_frame, gray_marker = tuple(cv.cvtColor(img, cv.COLOR_RGB2GRAY) for img in (frame, marker.color_channel))
    result = cv.matchTemplate(gray_frame, gray_marker, template_mode, mask=marker.alpha_channel)
  else:
    # all color averages the result from every colors
    # breaks upon invalid value found
    results = []
    split_images = [cv.split(img) for img in (frame, marker.color_channel)]

    for channel_frame, channel_marker in zip(*split_images):
      channel_result = cv.matchTemplate(channel_frame, channel_marker, template_mode, mask=marker.alpha_channel)
      results.append(channel_result)
      if not np.all(np.isfinite(channel_result)):
        break

    result = functools.reduce(lambda x, y: x + y, results) / len(results)

  condition = (result >= detection_threshold) & np.isfinite(result)
  threshold_table = result[condition]
  coord_data = np.where(condition)
  coords = list(zip(*coord_data[::-1]))
  invalid_count = np.count_nonzero(~np.isfinite(result))
  invalid_check = any([
    invalid_count > 0, # NaNcheck
    len(coords) > 100, # Over-detection (False Positive)
  ])

  found = bool(coords) and not invalid_check
  marker_result = MarkerResult(marker, found)
  if found:
    if debug_flags.SHOW_MARKER_DETECTION:
      log.debug(
        'found marker %s at threshold %7.3f. %7.3f~%7.3f',
        marker.name,
        detection_threshold * 100,
        threshold_table.min() * 100, threshold_table.max() * 100,
      )
    marker_result.coords = coords
  else:
    pass
  return marker_result

Markers : dict[MarkerName, Marker] = load_markers()
