from .simple import *
from .log import *
from .args import *
from .collections import *
from .version import *

def all_or_all(module):
  if hasattr(module, '__all__'):
    return list(module.__all__)
  else:
    from builtins import set as _set
    current_globals = _set([
      '__name__', '__doc__', '__package__',
      '__loader__', '__spec__', '__path__', '__file__',
      '__cached__', '__builtins__',
    ])
    module_globals = _set(k for k in dir(module))
    return list(module_globals - current_globals)

__all__ = \
  all_or_all(simple) + \
  all_or_all(log) + \
  all_or_all(args) + \
  all_or_all(collections) + \
  all_or_all(version)
