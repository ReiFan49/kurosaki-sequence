import sys
import enum

if sys.version_info < (3, 11):
  class StrEnum(str, enum.ReprEnum):
    pass
else:
  StrEnum = enum.StrEnum

del sys, enum
