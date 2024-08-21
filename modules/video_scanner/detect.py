# ruff: noqa: F821
import logging

import numpy as np
import cv2 as cv

# from .marker import Markers
from .state import VideoState, VideoFrameEvent
from . import utils

log = logging.getLogger(__name__)

class ColorCycle:
  _default_slope_point_ = 2
  _max_value_ = 255

  def __init__(self, state : int = None, slope_point : int  = None):
    self.slope_point = slope_point if isinstance(slope_point, int) and slope_point > 0 else self._default_slope_point_
    self.state = state if isinstance(state, int) else -1

  def __iter__(self):
    return self

  def __next__(self) -> tuple[int, int, int]:
    self.state += 1

    slope_repeat = self.slope_point * 6
    def slope(offset):
      offset_step = (offset - 1) * self.slope_point
      adjusted_state = (self.state + offset_step) % slope_repeat
      if adjusted_state < 3 * self.slope_point:
        value = int(2 * self._max_value_ - 3 * self._max_value_ * (adjusted_state / self.slope_point))
      else:
        value = int((-1) * self._max_value_ + 3 * self._max_value_ * ((adjusted_state - 3 * self.slope_point) / self.slope_point))
      return max(0, min(self._max_value_, value))

    b, g, r = slope(+2), slope(-2), slope(0)
    return b, g, r

  def __enter__(self):
    return self

  def __exit__(self, ex_type, ex_value, ex_trace):
    return False

def evaluate_now(f):
  return f()

def ensure_marker(*markers : str):
  def decorator(f):
    def wrapper(frame_event : VideoFrameEvent, frame : np.ndarray):
      if not any(marker in frame_event.marker_results for marker in markers):
        return
      f(frame_event, frame)
    wrapper.__name__ = f.__name__
    wrapper.__required_markers__ = markers
    return wrapper

  return decorator

def state_change_event(f):
  if f not in VideoFrameEvent.state_change_events:
    VideoFrameEvent.state_change_events.append(f)
  return f

@state_change_event
@ensure_marker('formation-icons')
def process_detect_unit_formation(frame_event : VideoFrameEvent, frame : np.ndarray):
  marker_result = frame_event.marker_results['formation-icons']

  actual_found = marker_result.ok
  if actual_found and not frame_event.frame_data[VideoState.UNIT_SELECT]:
    pass

  frame_event[VideoState.UNIT_SELECT] = actual_found

@state_change_event
@ensure_marker('global-loading')
def process_detect_loading_marker(frame_event, frame):
  marker_result = frame_event.marker_results['global-loading']

  actual_found = marker_result.ok
  if actual_found and not frame_event.frame_data[VideoState.LOADING_FLAG]:
    pass

  frame_event[VideoState.LOADING_FLAG] = actual_found

@state_change_event
def process_detect_loading_screen(frame_event, frame):
  def effective_flag(state):
    return frame_event[state] if frame_event[state] is not None else frame_event.frame_data[state]

  loading_flag = effective_flag(VideoState.LOADING_FLAG)
  screen_dark  = effective_flag(VideoState.SCREEN_DARK)

  frame_event[VideoState.LOADING_SCREEN] = loading_flag and screen_dark

@state_change_event
@ensure_marker('battle-icon-clock', 'battle-icon-pause')
def process_detect_gameplay_screen(frame_event : VideoFrameEvent, frame : np.ndarray):
  keys = ('battle-icon-clock', 'battle-icon-pause')
  marker_results = dict((name, result) for name, result in frame_event.marker_results.items() if name in keys)
  # detect_frame = frame.copy()
  actual_found = all(result.ok for result in marker_results.values())

  for key, color in zip(keys, ColorCycle()):
    marker_result = marker_results[key]

    if marker_result.ok and not frame_event.frame_data[VideoState.GAMEPLAY_DETECT]:
      pass

  if actual_found and not frame_event.frame_data[VideoState.GAMEPLAY_DETECT]:
    pass

  frame_event[VideoState.GAMEPLAY_DETECT] = actual_found

@state_change_event
@ensure_marker('battle-result-victory', 'battle-result-defeat')
def process_detect_gameplay_result(frame_event : VideoFrameEvent, frame : np.ndarray):
  states = (VideoState.GAMEPLAY_CONCLUDE_SUCCESS, VideoState.GAMEPLAY_CONCLUDE_FAILURE)
  keys = ('battle-result-victory', 'battle-result-defeat')
  marker_results = dict((name, result) for name, result in frame_event.marker_results.items() if name in keys)
  # detect_frame = frame.copy()
  actual_found = any(result.ok for result in marker_results.values())

  for state, key, color in zip(states, keys, ColorCycle()):
    marker_result = marker_results[key]

    if marker_result.ok and not frame_event.frame_data[state]:
      pass

  if actual_found:
    pass

  frame_event.update(dict(
    (state, marker_results[key].ok)
    for state, key in zip(states, keys)
  ))

@evaluate_now
def process_victory_screen():
  last_frame = None
  last_state_time : dict[VideoState, int] = {}

  def state_recorded(state : VideoState, states_dict):
    return state in last_state_time and not states_dict[state]

  def state_not_recorded(state : VideoState, states_dict):
    return state not in last_state_time

  @state_change_event
  def process_detect_victory_transition(frame_event : VideoFrameEvent, frame : np.ndarray):
    nonlocal last_frame, last_state_time
    frame_data = frame_event.frame_data
    n, fps = frame_event.frame_data.params['time']
    if frame_data.params['first_frame']:
      last_frame = frame

    # do not process exact frame
    if np.all(frame == last_frame):
      return

    score = utils.calculate_similarity(last_frame, frame)
    if state_recorded(VideoState.GAMEPLAY_DETECT, frame_data):
      frame_event[VideoState.GAMEPLAY_CONCLUDE_WAIT] = n > last_state_time[VideoState.GAMEPLAY_DETECT] + 5 * fps

    # Lock the Result state once set
    if VideoState.GAMEPLAY_CONCLUDE_RESULT in last_state_time:
      ...
    # After detecting Gameplay Success, make sure similarity score under 60.
    elif state_recorded(VideoState.GAMEPLAY_CONCLUDE_SUCCESS, frame_data) and \
      VideoState.GAMEPLAY_CONCLUDE_RESULT not in last_state_time:
      frame_event[VideoState.GAMEPLAY_CONCLUDE_RESULT] = score <= 60 and n > last_state_time[VideoState.GAMEPLAY_CONCLUDE_SUCCESS] + 2 * fps
      last_state_time[VideoState.GAMEPLAY_CONCLUDE_RESULT] = n

    if frame_event[VideoState.GAMEPLAY_CONCLUDE_RESULT]:
      frame_event[VideoState.GAMEPLAY_CONCLUDE_WAIT] = False

    last_frame = frame

  @state_change_event
  def track_last_active_state(frame_event : VideoFrameEvent, frame : np.ndarray):
    nonlocal last_state_time
    n, fps = frame_event.frame_data.params['time']

    # track state active time (in frame)
    last_state_time.update({
      k: n
      for k, v in frame_event.states.items()
      if v is True
    })

  return process_detect_victory_transition

@evaluate_now
def process_black_screen():
  loading_mask = None
  ignore_first_change = True
  @state_change_event
  def process_black_screen_check(frame_event : VideoFrameEvent, frame : np.ndarray):
    nonlocal loading_mask, ignore_first_change
    if frame_event.frame_data.params['first_frame']:
      loading_mask = None
      ignore_first_change = True

    def create_rectangle_mask(frame, offset, color):
      mask = np.full(frame.shape[:2], 255, dtype='uint8')
      cv.rectangle(
        mask,
        (offset, offset),
        (frame.shape[0] - offset, frame.shape[1] - offset),
        color,
        -1,
      )
      return mask

    # Darkness constants
    DARK_VALUE_THRESHOLD = 5
    DARK_DOMINANCE_THRESHOLD = 70
    DARK_COMPLETE_THRESHOLD = 95

    if loading_mask is None:
      loading_mask = create_rectangle_mask(frame, 80, 0)

    gray_frame = cv.cvtColor(frame, cv.COLOR_RGB2GRAY)
    gray_hist  = cv.calcHist([gray_frame], [0], loading_mask, [256], [0, 256])

    total_dark_pixels = gray_hist[:DARK_VALUE_THRESHOLD].sum()
    ratio_dark_pixels = total_dark_pixels / gray_hist.sum()
    is_gray_dark  = ratio_dark_pixels * 100 >= DARK_DOMINANCE_THRESHOLD
    is_gray_black = ratio_dark_pixels * 100 >= DARK_COMPLETE_THRESHOLD

    if ignore_first_change:
      frame_event.frame_data.states[VideoState.SCREEN_DARK], frame_event.frame_data.states[VideoState.SCREEN_BLACK] = is_gray_dark, is_gray_black
      ignore_first_change = False

    frame_event.update(
      (VideoState.SCREEN_DARK, is_gray_dark),
      (VideoState.SCREEN_BLACK, is_gray_black),
    )

  return process_black_screen_check

del ensure_marker, state_change_event
