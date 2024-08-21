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
  Instructs to support a file to render.
  '''
  def __init__(self, file: str):
    super().__init__()
    self.file : str = file

class RenderVideo(RenderFileSupport, RenderBase):
  '''
  Instructs to support video rendering.

  This allows splicing of given file.
  '''
  def __init__(self, start_time: float, end_time: float, file: str):
    super().__init__(file)
    self.start_time : float = start_time
    self.end_time   : float = end_time

class RenderStatic(RenderFileSupport, RenderBase):
  '''
  Instructs to support static image/file rendering.
  '''
  def __init__(self, file: str):
    super().__init__(file)

class RenderSpecial(RenderBase):
  '''
  Collection of special rendering instructions.
  '''
  pass

class RenderColorScreen(RenderSpecial):
  '''
  Instructs to render a static color.
  '''
  def __init__(self, color: str, width: int, height: int, fps: float):
    super().__init__()
    self.color  : str   = color
    self.width  : int   = width
    self.height : int   = height
    self.fps    : float = fps

class RenderBlackScreen(RenderColorScreen):
  '''
  Instructs to render a static black background.
  '''
  def __init__(self, width: int, height: int, fps: float):
    super().__init__('black', width, height, fps)

class RenderIgnore(RenderSpecial):
  '''
  Instructs to render nothing.
  '''
  pass

__all__ = (
  'RenderVideo', 'RenderStatic', 'RenderSpecial', 'RenderIgnore',
  'RenderColorScreen', 'RenderBlackScreen',
)
