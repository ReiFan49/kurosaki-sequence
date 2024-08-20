import enum
import typing
import logging
from dataclasses import dataclass

import numpy as np
import cv2 as cv

from .marker import (
  # Marker,
  MarkerResult,
  MarkerName,
  Markers,
  detect_frame_with_marker,
)

log = logging.getLogger(__name__)

class VideoState(enum.Enum):
  SCREEN_DARK  = enum.auto()
  SCREEN_BLACK = enum.auto()
  LOADING_FLAG = enum.auto()

  # unit formation icon check
  UNIT_SELECT = enum.auto()
  # loading screen check
  LOADING_SCREEN = enum.auto()
  # gameplay detection check
  GAMEPLAY_DETECT = enum.auto()
  # gameplay last-frame check
  GAMEPLAY_CONCLUDE_WAIT = enum.auto()
  # VICTORY state
  GAMEPLAY_CONCLUDE_SUCCESS = enum.auto()
  # DEFEAT state
  GAMEPLAY_CONCLUDE_FAILURE = enum.auto()
  # gameplay conclude result screen
  GAMEPLAY_CONCLUDE_RESULT = enum.auto()
  # recording cutoff
  RECORDING_CUTOFF = enum.auto()
  # end-of-file
  EOF = enum.auto()

VideoState.ANY = object()
VideoState.GAMEPLAY_CONCLUDE_STATES = tuple(x for x in VideoState if x.name.startswith('GAMEPLAY_CONCLUDE_'))

class VideoStateDict():
  def __init__(self, initial_state : typing.Optional[bool] = False):
    self.states = dict((k, bool(initial_state) if initial_state is not None else initial_state) for k in VideoState)

  def toggle(self, state: VideoState):
    if state not in self:
      return
    self[state] = not self[state]

  def __contains__(self, state: VideoState):
    return state in self.states

  def __getitem__(self, state: VideoState):
    if state not in self:
      return
    return self.states[state]

  def __setitem__(self, state: VideoState, value: bool):
    if state not in self:
      return
    # old_value = self.states[state]
    new_value = bool(value) if value is not None else None
    self.states[state] = new_value

  def update(self, *state_pair: dict[VideoState, bool] | tuple[VideoState, bool]):
    if isinstance(state_pair[0], dict):
      state_pair = state_pair[0].items()

    state_pair = [(state, bool(value)) for state, value in state_pair if isinstance(state, VideoState) and value is not None]
    relevant_keys = [state for state, value in state_pair]
    relevant_values = [value for state, value in self.states.items() if state in relevant_keys]
    after_values = [value for state, value in state_pair]

    if relevant_values != after_values:
      changed_map = dict((state, value) for state, value in state_pair if state not in self.states or value != self.states.get(state, None))
      self.states.update(changed_map)

class VideoFrameData(VideoStateDict):
  def __init__(self):
    super().__init__(False)
    self.params = {}
    self.hooks = []

  def __setitem__(self, state, value):
    if state not in self:
      return
    old_value = self.states[state]
    super().__setitem__(state, value)
    new_value = self.states[state]

    if old_value != new_value:
      self._trigger_hooks_(dict([(state, new_value)]))

  def update(self, *state_pair: dict[VideoState, bool] | tuple[VideoState, bool]):
    old_values = self.states.copy()
    super().update(*state_pair)
    new_values = self.states.copy()

    if old_values != new_values:
      changed_map = dict((key, new_values[key]) for key in set(old_values.keys()) | set(new_values.keys()) if key not in old_values or old_values[key] != new_values[key])
      self._trigger_hooks_(changed_map)

  def _trigger_hooks_(self, state_map: dict[VideoState, bool]):
    for hook in self.hooks:
      if not callable(hook):
        continue
      try:
        hook(state_map, params = self.params)
      except Exception:
        logging.error('Error detected on hook, ignoring.', exc_info=True)

class VideoFrameEvent(VideoStateDict):
  default_marker_settings = {
    'single_color_mode': False,
    'template_mode': cv.TM_CCOEFF_NORMED,
  }

  specific_marker_settings = {
    'battle-icon-clock': {
      'single_color_mode': True, 'detection_threshold': 0.92,
      'detection_region': (slice(0.6, None), slice(0.2)),
    },
    'battle-icon-pause': {
      'single_color_mode': True, 'detection_threshold': 0.8,
      'detection_region': (slice(0.6, None), slice(0.2)),
    },
    'battle-result-victory': { 'detection_threshold': 0.8 },
    # 'battle-result-defeat': { 'detection_threshold': 0.9 },
    'global-loading': {
      'single_color_mode': True,
      'detection_region': (slice(0.5, None), slice(0.8, None)),
    },
  }

  state_change_events = []

  def __init__(self, frame_data : VideoFrameData):
    super().__init__(None)
    self.frame_data = frame_data
    self.marker_results : dict[str, MarkerResult] = dict()

  def check_marker_relevance(self, marker_name : MarkerName) -> bool:
    any_markers = object()
    relevant_markers = set(
      marker
      for f in self.state_change_events
      for marker in (
        f.__required_markers__
        if hasattr(f, '__required_markers__')
        else set([any_markers])
      )
    )
    if not relevant_markers or any_markers in relevant_markers:
      return True
    return marker_name in relevant_markers

  def detect_markers_in_frame(self, frame):
    self.marker_results = dict()
    for name, marker in Markers.items():
      if not self.check_marker_relevance(name):
        continue
      marker_settings = dict()
      marker_settings.update(self.default_marker_settings)
      if name in self.specific_marker_settings:
        marker_settings.update(self.specific_marker_settings[name])

      self.marker_results[name] = detect_frame_with_marker(frame, marker, **marker_settings)

  def prepare_state_changes_in_frame(self, frame):
    # reset state changes to None
    super().__init__(None)

    for fun in self.state_change_events:
      fun(self, frame)

    self.frame_data.update(self.states)

@dataclass(slots=True, frozen=True)
class StateHook:
  states : frozenset[VideoState]
  callback : typing.Callable[[VideoFrameEvent, np.ndarray], typing.NoReturn]

  def __call__(self, states : dict, *, params = None):
    relevant_states = dict(
      (state, value)
      for state, value in states.items()
      if state in self.states
    )
    if relevant_states:
      self.callback(relevant_states, params = params)

def hook_for_states(*states) -> typing.Callable[typing.Callable, StateHook]:
  if VideoState.ANY in states:
    states = frozenset(VideoState)
  else:
    states = frozenset(state for state in states if isinstance(state, VideoState))

  def noop(*args):
    return

  if states:
    def decorator(f):
      return StateHook(states, f)
  else:
    def decorator(f):
      return noop

  return decorator
