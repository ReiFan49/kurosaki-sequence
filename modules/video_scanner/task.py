import contextlib
import logging
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import cv2 as cv

from modules.types import Fraction
from .state import VideoState, VideoFrameData, VideoFrameEvent
from .task_data import StateData
from . import frame_hooks
from . import task_frame_hooks
from . import utils
from modules import debug_flags

log = logging.getLogger(__name__)
FRAME_SKIP_SIMILAR_THRESHOLD = 98.0

def check_similarity(previous_frame, current_frame, *, threshold = FRAME_SKIP_SIMILAR_THRESHOLD):
  return utils.calculate_similarity(previous_frame, current_frame) >= threshold

@dataclass(slots=True)
class ScanState():
  '''
  Scan State object.

  An object that represents a frame and event changes surrounding given frame.
  '''
  frame : np.ndarray = field(repr=False)
  frame_event : VideoFrameEvent

  @property
  def frame_data(self):
    return self.frame_event.frame_data

  def process(self):
    self.frame_event.detect_markers_in_frame(self.frame)
    self.frame_event.prepare_state_changes_in_frame(self.frame)
    self.frame_data.update(self.frame_event.states)

class Scanner():
  '''
  Scanner object.

  A class that defines Video Scanner environment.
  '''

  def __init__(self, video_file, *, seek_option = None):
    self.frame_count = 0
    self.frame_rate = 30
    self.frame_data = None
    self.frame_cache = []

    if isinstance(seek_option, tuple) and len(seek_option) >= 2:
      self.frame_start_seek = tuple(seek_option[:2])
    else:
      self.frame_start_seek = None

    self.video_file = video_file
    self.video = None

    self.__init_transient_variables__()

  def __init_transient_variables__(self):
    '''
    Initialize transient variable state.
    '''
    self.state_logs = []

    if self.frame_data is None or self.frame_data.params: # do not reinitialize frame data
      self.frame_data = VideoFrameData()
      self.__init_frame_data_hooks__()

    self.frame_cache = []
    self.skip_history = deque(maxlen=100)
    self.iter_count = -1

  def __init_frame_data_hooks__(self):
    '''
    Initialize object specific frame hook.
    '''
    frame_data = self.frame_data
    frame_data.hooks.extend([
      frame_hooks.state_logger,
    ])
    self.hook_for_scanner()
    log.debug('Installed %d hook(s) on Scanner Frame Data.', len(frame_data.hooks))

  def hook_for_scanner(self):
    task_frame_hooks.apply_state_logger(self)
    task_frame_hooks.apply_state_logger_unconclude(self)

  @property
  def time(self):
    return (self.frame_count, self.frame_rate)

  @property
  def params(self):
    return {
      'time': self.time,
      'first_frame': self.iter_count < 1,
    }

  def __iter__(self):
    return self

  def __next__(self):
    if self.video is None:
      return None

    if not self.video.isOpened():
      raise StopIteration('Video is not yet opened')

    similar_threshold = utils.calculate_similarity_threshold(self, FRAME_SKIP_SIMILAR_THRESHOLD, 0.15)

    skip_count = 0
    while True: # Find until not similar or EoF
      ret, frame = self.video.read()
      if not ret:
        self.frame_count += skip_count
        raise StopIteration()

      if len(self.frame_cache) >= 1 and check_similarity(self.frame_cache[-1], frame, threshold = similar_threshold):
        skip_count += 1
        continue

      self.frame_cache.append(frame)
      while len(self.frame_cache) > 2:
        self.frame_cache.pop(0)

      break

    if skip_count > 0 and debug_flags.SHOW_SKIPPED_FRAMES:
      log.debug('%d frames skipped at %df (threshold %.2f)', skip_count, self.frame_count, similar_threshold)
    self.skip_history.append(skip_count)

    self.frame_count, self.frame_rate = \
      int(self.video.get(cv.CAP_PROP_POS_FRAMES) - 1), self.video.get(cv.CAP_PROP_FPS)
    self.iter_count += 1
    self.frame_data.params = self.params

    return ScanState(frame, VideoFrameEvent(self.frame_data))

  def __enter__(self):
    self.__init_transient_variables__()
    self.video = cv.VideoCapture(self.video_file)

    # Apply seeking if necessary
    if self.frame_start_seek is not None:
      seek_type, seek_value = self.frame_start_seek
      if seek_type in (cv.CAP_PROP_POS_MSEC, cv.CAP_PROP_POS_FRAMES):
        self.video.set(seek_type, seek_value)

    return self, self.video

  def __exit__(self, *exc):
    if self.frame_count >= 0:
      self.state_logs.append(StateData(
        Fraction(self.frame_count, int(self.frame_rate)),
        {VideoState.EOF: True},
      ))

    self.video.release()
    self.frame_count = -1
    return False

@contextlib.contextmanager
def open_video_file(file):
  '''
  Opens video file manually without using Video Scan object.
  '''
  video = cv.VideoCapture(file)

  try:
    yield video
  finally:
    video.release()
