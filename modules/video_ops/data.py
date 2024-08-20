import typing as t

def force_list(obj: t.Union[t.List, t.Any]):
  if isinstance(obj, list):
    return obj
  return []

class Segment():
  pass

class RenderBase():
  def __init__(self):
    pass

  def __repr__(self):
    return '{0}({1})'.format(
      self.__class__.__name__,
      ', '.join(
        '{0}={1!r}'.format(k, v)
        for k, v in self.__dict__.items()
      ),
    )

class RenderFileSupport():
  '''
  render with file support
  '''
  def __init__(self, file: str):
    super().__init__()
    self.file : str = file

class RenderVideo(RenderFileSupport, RenderBase):
  '''
  render video
  '''
  def __init__(self, start_time: float, end_time: float, file: str):
    super().__init__(file)
    self.start_time : float = start_time
    self.end_time   : float = end_time

class RenderStatic(RenderFileSupport, RenderBase):
  '''
  render static file/image
  '''
  def __init__(self, file: str):
    super().__init__(file)

class RenderSpecial(RenderBase):
  '''
  render special instruction
  '''
  pass

class RenderColorScreen(RenderSpecial):
  '''
  render special static color
  '''
  def __init__(self, color: str, width: int, height: int, fps: float):
    super().__init__()
    self.color  : str   = color
    self.width  : int   = width
    self.height : int   = height
    self.fps    : float = fps

class RenderBlackScreen(RenderColorScreen):
  '''
  render special static black screen
  '''
  def __init__(self, width: int, height: int, fps: float):
    super().__init__('black', width, height, fps)

class RenderIgnore(RenderSpecial):
  '''
  render special object to ignore
  '''
  pass

__all__ = (
  'RenderVideo', 'RenderStatic', 'RenderSpecial', 'RenderIgnore',
  'RenderColorScreen', 'RenderBlackScreen',
)
