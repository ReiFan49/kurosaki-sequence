import functools

@functools.singledispatch
def force_list(obj) -> list:
  '''
  Forces out fed object to be list.
  '''
  return []

@force_list.register
def _(obj: list) -> list:
  return obj

FFMPEG_VERSION = (0, 0, 0, None)

def obtain_version():
  import subprocess
  version_string = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True).stdout.split()[2]
  del globals()['obtain_version']

  version_number, version_alt = version_string.split('-', 1)
  version_tuple = tuple(int(x) for x in version_number.split('.'))

  global FFMPEG_VERSION
  FFMPEG_VERSION = (*version_tuple, version_alt)

obtain_version()
