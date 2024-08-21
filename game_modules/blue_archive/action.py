import os
import sys # noqa: F401
import math
import json
import logging
import argparse
from enum import Enum, auto

import numpy as np

from modules import task
from modules.utils import (
  set as unify_list,
)
from modules.types import Fraction, Timespan
from modules.types.__compatibilities__.enum import StrEnum
from modules.video_scanner.state import VideoState
from modules import debug_flags

log = logging.getLogger(__name__)

class DebugMode(Enum):
  AUTO = 0
  FORCE_ENABLE = auto()
  FORCE_DISABLE = auto()

class DebugFiles(StrEnum):
  STATES = '_debug/blue_archive_states.py'
  SPLITS = '_debug/blue_archive_splits.py'

class VideoSegment(Enum):
  '''
  VideoSegment represents video key segment of a Blue Archive Video file.
  '''
  UNIT_SELECTION = auto()
  LOADING_SCREEN = auto()
  GAMEPLAY_SCREEN = auto()

  # Optional: split used for transition that takes longer than 5 seconds
  GAMEPLAY_CONCLUDE = auto()
  # Optional: split used for transition that takes longer than 2 seconds
  GAMEPLAY_RESULT = auto()

class SegmentEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, Timespan):
      return (obj.start, obj.end)
    if isinstance(obj, Fraction):
      return list(obj)
    if isinstance(obj, Enum):
      return obj.value
    return super().default(obj)

VideoSegment.mandatory = [
  VideoSegment.UNIT_SELECTION,
  VideoSegment.LOADING_SCREEN,
  VideoSegment.GAMEPLAY_SCREEN,
]

INTRO_CUTOFF      = Fraction(3, 1) # 3.0
INTRO_CUTOFF_RATE = Fraction(2, 2) # 1.0
GAME_CUTOFF_RATE  = Fraction(2, 2) # 1.0

GAME_DELAY_CONCLUDE_WAIT = (5, 2)

# Segment Debug Modifier should left disabled
# when not doing Cutoff Split explicitly.
SEGMENT_DEBUG_MODIFIER = DebugMode.FORCE_DISABLE
# Splits Debug Modifier should left automatically check.
SPLITS_DEBUG_MODIFIER = DebugMode.AUTO

def obtain_event_data(file):
  '''
  Create state data or loads it.

  Branching only used for debugging.
  '''
  default_mode = not os.path.exists(DebugFiles.STATES)
  if SEGMENT_DEBUG_MODIFIER is not DebugMode.AUTO:
    if default_mode and SEGMENT_DEBUG_MODIFIER is DebugMode.FORCE_ENABLE:
      log.error('Pre-calculated state file is not found. Disabling debug mode.')
    else:
      default_mode = SEGMENT_DEBUG_MODIFIER == DebugMode.FORCE_DISABLE

  if default_mode:
    return task.scan_video_timing(file)
  else:
    import importlib
    global_plus = {}
    global_plus['Fraction'] = Fraction
    global_plus['StateData'] = importlib.import_module('modules.video_scanner.task').StateData
    global_plus['VideoState'] = VideoState
    global_plus['output'] = None
    exec(
      compile(
        open(DebugFiles.STATES).read(),
        DebugFiles.STATES,
        'exec',
      ), global_plus,
    )
    assert global_plus['output'] is not None
    return global_plus['output']

def convert_state_to_matrix(state_events):
  time = np.array([state_event.time for state_event in state_events])
  state_count = len(VideoState)
  states = np.array([])

  for state_event in state_events:
    state_vector = np.full(state_count, -1)
    vector_indices = [state.value - 1 for state in state_event.states.keys()]
    vector_values = [int(state_value) for state_value in state_event.states.values()]
    np.put(state_vector, vector_indices, vector_values)
    states = np.vstack((*states, state_vector))

  return time, states

def scan_video_points(file):
  event_times, event_changes = convert_state_to_matrix(obtain_event_data(file))

  # Store EOF frame count and remove EOF state flag
  end_point = next((y for y, x in zip(*np.where(event_changes == 1)) if x == VideoState.EOF.value - 1), None)
  end_frame = event_times[end_point]
  event_changes = event_changes[:, :-1]

  # Remove all noop times
  remove_empty_rows = ~np.all(event_changes == -1, axis = 1)
  event_times, event_changes = [a[remove_empty_rows] for a in (event_times, event_changes)]

  if debug_flags.SHOW_SCANNED_SPLITS:
    print(file)
    for event_time, event_time_changes in zip(event_times, event_changes):
      print(event_time, event_time_changes)

  # Create bounded timespan object
  def new_timespan():
    return Timespan(Fraction(0, end_frame.denominator), end_frame)
  # Create mandatory keys and alternate keys
  split_keys: dict[VideoSegment, Timespan[Fraction]] = {
    k: new_timespan()
    for k in VideoSegment.mandatory
  }
  split_alternate: dict[VideoSegment, Timespan[Fraction]] = {
    k: new_timespan()
    for k in VideoSegment
  }
  null_time = new_timespan()
  loading_occurrence = 0

  # Process event set and unset flags
  for time, event_change in zip(event_times, event_changes):
    event_unset, event_set = [
      set(
        VideoState(x + 1)
        for (x, ) in zip(*np.where(event_change == c))
      )
      for c in (0, 1)
    ]

    if VideoState.UNIT_SELECT in event_set:
      split_keys[VideoSegment.UNIT_SELECTION].start = time
    elif VideoState.UNIT_SELECT in event_unset:
      split_keys[VideoSegment.UNIT_SELECTION].end = time

    if VideoState.LOADING_SCREEN in event_set:
      loading_offset = 1 if loading_occurrence > 0 else 0
      split_keys[VideoSegment.LOADING_SCREEN].start = time + loading_offset
      split_keys[VideoSegment.LOADING_SCREEN].end = time + 1 + loading_offset

      loading_occurrence += 1
    elif VideoState.LOADING_SCREEN in event_unset:
      split_keys[VideoSegment.GAMEPLAY_SCREEN].start = time

    if VideoState.GAMEPLAY_DETECT in event_set and \
      split_keys[VideoSegment.GAMEPLAY_SCREEN].start < split_keys[VideoSegment.LOADING_SCREEN].end:
      split_keys[VideoSegment.GAMEPLAY_SCREEN].start = time
    elif VideoState.GAMEPLAY_DETECT in event_unset:
      split_alternate[VideoSegment.GAMEPLAY_SCREEN].end = time

    if any(state in event_unset for state in (
      VideoState.GAMEPLAY_CONCLUDE_SUCCESS,
      VideoState.GAMEPLAY_CONCLUDE_FAILURE,
    )):
      split_alternate[VideoSegment.GAMEPLAY_CONCLUDE].start = time - Fraction(75, 60)

    if VideoState.GAMEPLAY_CONCLUDE_RESULT in event_set:
      split_alternate[VideoSegment.GAMEPLAY_CONCLUDE].end = time
      split_alternate[VideoSegment.GAMEPLAY_RESULT].start = time

    # Cuts processing after getting recording cutoff flag
    if VideoState.RECORDING_CUTOFF in event_set:
      split_keys[VideoSegment.GAMEPLAY_SCREEN].end = time
      break

  # Process alternate keys if needed
  del_alternate = {k for k, v in split_alternate.items() if v == null_time}
  for k in del_alternate:
    del split_alternate[k]

  if VideoSegment.GAMEPLAY_SCREEN in split_alternate:
    split_alternate[VideoSegment.GAMEPLAY_SCREEN].start = split_alternate[VideoSegment.GAMEPLAY_SCREEN].end
    split_alternate[VideoSegment.GAMEPLAY_SCREEN].duration = 5

  special_segments = (
    VideoSegment.GAMEPLAY_SCREEN,
    VideoSegment.GAMEPLAY_CONCLUDE,
    VideoSegment.GAMEPLAY_RESULT,
  )
  special_segments = tuple(k for k in special_segments if k in split_alternate)

  # adjust special segments
  # whether to merge or split it
  # whether to keep it or cut it
  for i, last_segment, segment in reversed(list(zip(
    range(len(special_segments[1:])),
    special_segments[0:],
    special_segments[1:],
  ))):
    if segment in split_alternate:
      # Merge segment if under the cutoff.
      transition_duration = split_alternate[segment].start - split_alternate[last_segment].start
      if transition_duration < GAME_DELAY_CONCLUDE_WAIT[i]:
        del split_alternate[segment]
      elif transition_duration > GAME_DELAY_CONCLUDE_WAIT[i]:
        split_alternate[last_segment].duration = GAME_DELAY_CONCLUDE_WAIT[i]

  # only apply pending GAMEPLAY end if alternate splices were detected.
  if len(split_alternate) > 1 and VideoSegment.GAMEPLAY_SCREEN in split_alternate:
    split_keys[VideoSegment.GAMEPLAY_SCREEN].end = split_alternate[VideoSegment.GAMEPLAY_SCREEN].end

  if debug_flags.SHOW_SCANNED_SPLITS:
    print('Original')
    for segment, time in split_keys.items():
      print(segment, time)

  for segment in split_alternate:
    if segment in split_keys:
      continue
    split_keys[segment] = split_alternate[segment]

  if debug_flags.SHOW_SCANNED_SPLITS:
    print('Merged')
    for segment, time in split_keys.items():
      print(segment, time)

  return split_keys

def convert_video_splits(*files):
  '''
  Processes further existing split data of each files.
  '''
  debug_mode = os.path.exists(DebugFiles.SPLITS)
  if debug_mode and SPLITS_DEBUG_MODIFIER is DebugMode.FORCE_DISABLE:
    debug_mode = False

  if not debug_mode:
    result = dict(
      (fn, scan_video_points(fn))
      for fn in files
    )
  else:
    exec_globals = {k: v for k, v in globals().items()}
    exec(
      compile(
        open(DebugFiles.SPLITS).read(),
        DebugFiles.SPLITS,
        'exec',
      ), exec_globals,
    )
    result = {
      fn: timing
      for fn, timing in exec_globals['output'].items()
      if fn in files
    }
    assert all(file in result for file in files), \
      'Please confirm every files has been registered into the splits.'

  # Equalize cutoff for every splits.
  current_cutoff = INTRO_CUTOFF
  for fn, timing in result.items():
    file_cutoff = timing[VideoSegment.UNIT_SELECTION].end
    if file_cutoff < current_cutoff:
      current_cutoff = int(file_cutoff / INTRO_CUTOFF_RATE) * INTRO_CUTOFF_RATE

  for fn, timing in result.items():
    timing[VideoSegment.UNIT_SELECTION].start = timing[VideoSegment.UNIT_SELECTION].end - current_cutoff
    last_segment = list(timing)[-1]
    rounded_segment = math.floor(
      float(timing[last_segment].end - timing[VideoSegment.GAMEPLAY_SCREEN].start) /
      float(GAME_CUTOFF_RATE)) * GAME_CUTOFF_RATE
    timing[last_segment].end = timing[VideoSegment.GAMEPLAY_SCREEN].start + rounded_segment

  return {
    'results': result,
  }

def set_debug_segment_flag(parsed):
  global SEGMENT_DEBUG_MODIFIER
  SEGMENT_DEBUG_MODIFIER = DebugMode.AUTO

  if 'cutoff_debug' in parsed:
    if parsed.cutoff_debug is True:
      log.info('Program will never scan the given video files.')
      SEGMENT_DEBUG_MODIFIER = DebugMode.FORCE_ENABLE
    elif parsed.cutoff_debug is False:
      log.info('Program will always scan the given video files.')
      SEGMENT_DEBUG_MODIFIER = DebugMode.FORCE_DISABLE

def execute_cutoff_detect(parsed):
  '''
  Scan and determine raw timespan of an event for a given file.
  '''
  set_debug_segment_flag(parsed)

  files = unify_list(parsed.files)
  splits = convert_video_splits(*files)
  splits['results'] = {
    fn: {
      k.name: v
      for k, v in d.items()
    }
    for fn, d in splits['results'].items()
  }
  output = json.dumps(splits, cls=SegmentEncoder)
  print(output)

def execute_raid_merge(parsed):
  video_files = parsed.files
  image_files = parsed.team_overlays or []
  video_splits = convert_video_splits(*video_files)

  for files, key in zip([image_files, video_files], ('image', 'video')):
    deduped = unify_list(files)
    assert len(files) == len(deduped), \
      'duplicate files detected on {} file list'.format(key)

  assert len(image_files) in (1, len(video_files)), \
    'expected image files either 1 or {}, given {}'.format(len(video_files), len(image_files))

  image_files[:] = image_files[:] * (len(video_files) // len(image_files))
  task.create_filter_script_raid(
    parsed.output_file,
    parsed.intro_file,
    video_files,
    image_files,
    video_splits['results'],
  )

def execute_jfd_merge(parsed):
  video_files = parsed.files
  image_files = parsed.team_overlays or [None]
  video_splits = convert_video_splits(*video_files)

  for files, key in zip([video_files], ('video')):
    deduped = unify_list(files)
    assert len(files) == len(deduped), \
      'duplicate files detected on {} file list'.format(key)

  jfd_options = argparse.Namespace(**{
    k[4:]: v for k, v in vars(parsed).items()
    if k.startswith('jfd_')
  })

  task.create_filter_script_jfd(
    parsed.output_file,
    parsed.intro_file,
    video_files,
    image_files[0],
    video_splits['results'],
    jfd_options,
  )
