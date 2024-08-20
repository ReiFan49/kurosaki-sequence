import os

def check_file(fn : str):
  if not os.path.exists(fn):
    raise ValueError('{}, file not found.'.format(fn))

  return fn

__all__ = (
  'check_file',
)
