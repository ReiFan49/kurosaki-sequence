import sys
import logging

def setup_logging(log):
  handler = logging.StreamHandler(stream=sys.stderr)
  formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {message}', '%Y-%m-%d %H:%M:%S', style='{')
  handler.setFormatter(formatter)
  log.addHandler(handler)
  log.setLevel(logging.INFO)

__all__ = (
  'setup_logging',
)
