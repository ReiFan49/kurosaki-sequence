import math
from enum import Enum
from typing import (
  Optional,
  Any,
)

from modules.video_ops import data

dictStrFree = dict[str, Any]
dictEnumTime = dict[Enum, Any]

class VideoTransform():
  '''
  Base definition of Video Transformation module.
  '''

  def __init__(
    self,
    *,
    video_files: list[str],
    image_files: list[str],
    intro_file:  Optional[str] = None,
    splits:      dict[str, dictEnumTime],
    output_file: str,
  ):
    '''
    Initialize VideoTransform class.

    Initializes blank and default variables,
    pass the input arguments to initialization function.
    '''
    self.segments : list[str] = []
    self.indices  : dict[str, int] = {}
    self.renders  : list[dictStrFree] = []
    self.options  : dict[str, Any] = {}

    self.initialize_data(
      video_files = video_files,
      image_files = image_files,
      intro_file  = intro_file,
      splits      = splits,
      output_file = output_file,
    )

  def __enter__(self):
    '''
    Opens up processing context.

    Context is used to prepare all required statements before processing it.
    '''
    return self

  def __exit__(self, exc_type, exc_value, exc_tb):
    self.process()
    return False

  def allocate_segments(self):
    '''
    Allocate video segments.

    By default the allocation is for FFMPEG.
    Subclasses should expect a set of duplicate file names
    to indicate splicing of video file.
    '''
    segments = [None]
    segments[1:] = [
      fn if i.value in self.file_segments[fn] else None
      for fn in self.video_files
      for i in self.split_segments
    ]
    segments[len(segments):] = [None] * (
      math.ceil(len(segments) / 10) * 10 - len(segments)
    )
    segments.append(self.intro_file)
    segments.extend(self.image_files)

    self.segments = segments

  def assign_indices(self):
    '''
    Assigns starting index of given filename.

    File list are assumed to be contiguous after processing the segment slots.
    '''
    indices = {}
    for file in [*self.video_files, self.intro_file, *self.image_files]:
      if file is None:
        continue
      indices[file] = self.segments.index(file)

    self.indices = indices

  def assign_segments(self):
    '''
    Assigns render functionality of each slots.

    Derived from it's FFMPEG counterpart,
    Rendering segments are composed of instruction for underlying
    module to process the input.
    '''
    render_segments = []
    for i, segment in enumerate(self.segments):
      # Special directive
      if segment is None:
        # Background
        if i == 0:
          # {'f': 'lavfi', 'i': 'color=c=black:s=1600x900:r=60'}
          render_segments.append(data.RenderBlackScreen(1600, 900, 60))
        # Slot Padding
        else:
          # {'f': 'lavfi', 'i': 'nullsrc'}
          render_segments.append(data.RenderIgnore())
        continue

      # Segment is Video file
      if segment in self.splits:
        base_index = self.indices[segment]
        split = self.splits[segment]
        key = sorted(list(split), key=lambda k: k.value)[(i - base_index)]
        time_data = split[key]
        # {
        #  'ss': round(data[0][0] / data[0][1], 3),
        #  'to': round(data[1][0] / data[1][1], 3),
        #   'i': segment,
        # }
        render_segments.append(data.RenderVideo(
          round(float(time_data.start), 3),
          round(float(time_data.end), 3),
          segment,
        ))
        continue

      # Segment is Image file
      # { 'i': segment }
      render_segments.append(data.RenderStatic(segment))

    self.renders = render_segments

  def assign_specifications(self):
    '''
    Assigns stream specifications.

    Used to store vital information of video files to be used by the module.
    '''
    pass

  def initialize_data(
    self,
    *,
    video_files: list[str],
    image_files: list[str],
    intro_file: Optional[str] = None,
    splits:   dict[str, dictEnumTime],
    output_file: str,
  ):
    '''
    Initialize state of Transformation object based on given file inputs.
    '''
    self.output_file = output_file

    self.video_files = list(video_files)
    self.image_files = list(image_files)
    self.intro_file  = intro_file
    self.splits      = dict(splits)

    self.split_segments = sorted(set(
      k
      for segments in splits.values()
      for k in list(segments)
    ), key=lambda k: k.value)
    self.file_segments = {
      fn: { k.value for k in segments }
      for fn, segments in splits.items()
    }

    self.allocate_segments()
    self.assign_indices()
    self.assign_segments()
    self.assign_specifications()

  def process(self):
    '''
    Implementation should be done by underlying subclass.
    '''
    raise NotImplementedError()

class VideoProcessor():
  '''
  Base definition of Video Processing module.

  This class processes data from Transformation module,
  based on its underlying engine.
  '''

  def __init__(self, tf: VideoTransform):
    self.tf = tf

  def process(self):
    raise NotImplementedError()
