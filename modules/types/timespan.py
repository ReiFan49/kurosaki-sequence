import typing
from dataclasses import dataclass
from numbers import Number, Rational # noqa: F401
from .fraction import Fraction

T = typing.TypeVar('T', int, float, Fraction)

@dataclass(slots=True)
class Timespan(typing.Generic[T]):
  '''
  Timespan class represents range of time defined by a number or tuple of two integers.
  '''

  start: T
  end: T

  @property
  def duration(self) -> T:
    return self.end - self.start

  @duration.setter
  def duration(self, value : T):
    if value <= 0:
      raise ValueError('duration must be positive')

    self.end = self.start + value

  def __contains__(self, value : T) -> bool:
    return self.start <= value and value <= self.end
  def __lt__(self, value : T) -> bool:
    return self.start < value
  def __le__(self, value : T) -> bool:
    return self.start <= value
  def __ge__(self, value : T) -> bool:
    return self.end >= value
  def __gt__(self, value : T) -> bool:
    return self.end > value

__all__ = (
  'Timespan',
)
