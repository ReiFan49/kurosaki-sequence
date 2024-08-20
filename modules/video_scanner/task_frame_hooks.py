from modules.types import Fraction
from .state import VideoState, hook_for_states
from .task_data import StateData

def hook_for_task_states(*states):
  '''
  Function Decorator for `Scanner` object binding.
  '''
  def hook_wrapper(f):
    def instance_wrapper(self):
      @hook_for_states(*states)
      def wrapped_call(states : dict, *, params : dict = None):
        f(self, states, params = params)

      self.frame_data.hooks.append(wrapped_call)
    instance_wrapper.__name__ = f.__name__
    return instance_wrapper
  return hook_wrapper

@hook_for_task_states(VideoState.ANY)
def apply_state_logger(self, states : dict, *, params : dict = None):
  '''
  Appends state changes to history.
  '''
  n, fps = params['time']
  self.state_logs.append(StateData(Fraction(n, int(fps)), states))

@hook_for_task_states(VideoState.GAMEPLAY_DETECT)
def apply_state_logger_unconclude(self, states : dict, *, params : dict = None):
  '''
  Cleanup unwanted conclusion states.
  '''
  n, fps = params['time']
  if states[VideoState.GAMEPLAY_DETECT] is not True:
    return

  ctime = Fraction(n, int(fps))
  for state_log in self.state_logs:
    if ctime >= state_log.time:
      continue

    for state in VideoState.GAMEPLAY_CONCLUDE_STATES:
      if state in state_log.states:
        del state_log.states[state]

__all__ = (
  'apply_state_logger',
  'apply_state_logger_unconclude',
)
