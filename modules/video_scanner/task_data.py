from dataclasses import dataclass

from modules.types import Fraction
from .state import VideoState

@dataclass(slots=True, frozen=True)
class StateData():
  '''
  Snapshot of state changing events.
  '''

  time : Fraction
  states : dict[VideoState, bool]

__all__ = (
  'StateData',
)
