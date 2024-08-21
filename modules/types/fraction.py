import math
from dataclasses import dataclass
import numbers

def is_tuple_of_fraction(value):
  return isinstance(value, tuple) and \
    tuple(type(x) for x in value) == (int, int)

@dataclass(slots=True, frozen=True)
class Fraction():
  '''
  Simple Fraction implementation.

  Preserves denominator rather than rationalizing
  whole of denominator.
  '''

  numerator : int
  denominator : int = 1

  def __post_init__(self):
    if any(
      not isinstance(expected_int, int)
      for expected_int in (self.numerator, self.denominator)
    ):
      raise TypeError('Fraction only supports integer-values')

    if self.denominator < 0:
      # self.numerator, self.denominator = -self.numerator, -self.denominator
      object.__setattr__(self, 'numerator', -self.numerator)
      object.__setattr__(self, 'denominator', -self.denominator)
    elif self.denominator == 0:
      raise ZeroDivisionError('division by zero')

  def __add__(self, other):
    if isinstance(other, Fraction):
      gcd = math.gcd(self.denominator, other.denominator)
      new_denominator = (self.denominator * other.denominator) // gcd
      new_numerator = (self.numerator * other.denominator // gcd) + \
                      (other.numerator * self.denominator // gcd)
      return Fraction(new_numerator, new_denominator)
    elif is_tuple_of_fraction(other):
      return self.__add__(Fraction(other[0], other[1]))
    elif isinstance(other, int):
      return Fraction(self.numerator + other * self.denominator, self.denominator)
    else:
      return NotImplemented
  def __sub__(self, other):
    if is_tuple_of_fraction(other):
      return self.__add__(-Fraction(other[0], other[1]))
    return self.__add__(-other)
  def __mul__(self, other):
    if isinstance(other, Fraction):
      gcd = math.gcd(self.denominator, other.denominator)
      return Fraction(
        self.numerator * other.numerator,
        self.denominator * other.denominator // gcd,
      )
    elif is_tuple_of_fraction(other):
      return self.__mul__(Fraction(other[0], other[1]))
    elif isinstance(other, int):
      return Fraction(self.numerator * other, self.denominator)
    else:
      return NotImplemented
  def __truediv__(self, other):
    if isinstance(other, Fraction):
      gcd = math.gcd(self.denominator, other.numerator)
      return Fraction(
        self.numerator * other.denominator,
        self.denominator * other.numerator // gcd,
      )
    elif is_tuple_of_fraction(other):
      return self.__truediv__(Fraction(other[0], other[1]))
    elif isinstance(other, int):
      return Fraction(self.numerator, self.denominator * other)
    else:
      return NotImplemented

  def __radd__(self, other):
    return self.__add__(other)
  def __rsub__(self, other):
    return self.__sub__(other)
  def __rmul__(self, other):
    return self.__mul__(other)
  def __rtruediv__(self, other):
    return self.__truediv__(other)

  def __compare__(self, other):
    if is_tuple_of_fraction(other):
      return self.__compare__(Fraction(other[0], other[1]))
    if self.denominator == other.denominator:
      raw_self, raw_other = (self.numerator, other.numerator)
    else:
      raw_self, raw_other = (float(self), float(other))

    if raw_self < raw_other:
      return -1
    elif raw_self > raw_other:
      return +1
    else:
      return  0

  def __lt__(self, other):
    return self.__compare__(other) < 0
  def __le__(self, other):
    return self.__compare__(other) <= 0
  def __eq__(self, other):
    return self.__compare__(other) == 0
  def __ne__(self, other):
    return self.__compare__(other) != 0
  def __ge__(self, other):
    return self.__compare__(other) >= 0
  def __gt__(self, other):
    return self.__compare__(other) > 0

  def __pos__(self):
    return self
  def __neg__(self):
    return Fraction(-self.numerator, self.denominator)
  def __abs__(self):
    if self.numerator >= 0:
      return self
    return Fraction(-self.numerator, self.denominator)

  def __int__(self):
    return self.numerator // self.denominator
  def __float__(self):
    return self.numerator / self.denominator
  def __bool__(self):
    return bool(self.numerator)
  def __repr__(self):
    return 'Fraction({0.numerator}/{0.denominator})'.format(self)
  def __str__(self):
    return '({0.numerator}/{0.denominator})'.format(self)

  def __iter__(self):
    return iter((self.numerator, self.denominator))

  def normalize_ratio(self, factor):
    '''
    Normalize ratio by given factor amount.

    a (9, 3) can be normalized by 1 and 3.
    a (10000, 250) can be normalized by any factor of 250.
    '''
    gcd = math.gcd(self.numerator, self.denominator)
    if gcd / factor == gcd // factor:
      return Fraction(
        self.numerator // factor,
        self.denominator // factor,
      )
    raise ValueError(f"{factor} is not a factor of {gcd}")

numbers.Rational.register(Fraction)
FractionInterface = tuple[int, int] | Fraction

__all__ = (
  'Fraction',
  'FractionInterface',
)
