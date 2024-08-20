import logging

log = logging.getLogger(__name__)

def python_version():
  import sys
  version = sys.version_info
  log.info('Python version: %d.%d.%d', version.major, version.minor, version.micro)

def ffmpeg_version():
  import subprocess
  try:
    proc = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
  except subprocess.CalledProcessError:
    log.warning('FFMPEG version: %s', '[Unknown]', exc_info=True)
  except Exception:
    log.warning('FFMPEG version: %s', '[Unknown]', exc_info=True)
  else:
    version = proc.stdout.split()[2]
    log.info('FFMPEG version: %s', version)

def opencv_version():
  import cv2 as cv
  log.info('OpenCV Version: %s', cv.__version__)

def print_versions():
  python_version()
  ffmpeg_version()
  opencv_version()

__all__ = (
  'print_versions',
  'python_version',
  'ffmpeg_version',
  'opencv_version',
)
