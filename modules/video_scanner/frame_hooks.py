import logging

from .state import VideoState, hook_for_states
from modules import debug_flags

log = logging.getLogger(__name__)

if debug_flags.SHOW_STATE_CHANGES:
  @hook_for_states(VideoState.ANY)
  def state_logger(states : dict, *, params : dict = None):
    for toggle_text, toggle_value in zip(('ON', 'OFF'), (True, False)):
      event_toggled = [state for state, value in states.items() if value is toggle_value]
      if not event_toggled:
        continue

      log.debug(
        '@ %s | %s %s',
        params['time'],
        toggle_text,
        ', '.join(str(state.name) for state in event_toggled),
      )
