from typing import Optional, Any, Sequence
from dataclasses import dataclass, field, KW_ONLY

from modules.types.__compatibilities__.enum import StrEnum
from .utils import *

class StreamType(StrEnum):
  VIDEO = 'v'
  AUDIO = 'a'

@dataclass(slots=True, frozen=True)
class StreamSpecification():
  width: int
  height: int
  pix_fmt: str
  r_frame_rate: str
  avg_frame_rate: str
  duration: float
  nb_frames: int

class StreamBase():
  pass

@dataclass(slots=True, order=True, frozen=True)
class Stream(StreamBase):
  id: int
  type: Optional[StreamType]
  stream: Optional[int] = None

  def __str__(self):
    return ':'.join(str(getattr(self, x)) for x in self.__slots__ if getattr(self, x) is not None)

@dataclass(slots=True, order=True, frozen=True)
class Label(StreamBase):
  name: str

  def __str__(self):
    return self.name

@dataclass(slots=True, frozen=True)
class Action:
  op: str
  _: KW_ONLY
  args: list[Any] = field(default_factory=list)
  params: dict[str, Any] = field(default_factory=dict)

  def __str__(self):
    def escape(s):
      '''
      Simple escape. Only for required scope.
      '''
      #if ',' in str(s):
      #  return "'" + str(s) + "'"
      return s

    self.__assert_late_expressions_evaluated()
    if not self.op:
      raise ValueError('op must not falsy value!')

    param_args = ':'.join(f'{k}={escape(v)}' for k, v in self.params.items())
    order_args = [escape(s) for s in self.args]
    comb_args = ':'.join(str(x) for x in (*order_args, param_args) if str(x))
    return '='.join(x for x in (self.op, comb_args) if str(x))

  @property
  def late_evaluation(self):
    return any(
      isinstance(arg, LateExpr)
      for arg in (*self.args, self.params.values())
    )

  def __assert_late_expressions_evaluated(self):
    if any(not expr.evaluated for expr in (*self.args, *self.params.values()) if isinstance(expr, LateExpr)):
      raise ValueError('some values not evaluated yet.')

class Graph:
  __slots__ = ('sources', 'targets', 'action')
  def __init__(
    self,
    sources: Sequence[StreamBase],
    targets: Sequence[StreamBase],
    action:  Action,
  ):
    self.sources = force_list(sources)
    self.targets = force_list(targets)
    self.action  = action

  def __str__(self):
    source_str, target_str = [
      ''.join(f'[{stream}]' for stream in streams)
      for streams in (self.sources, self.targets)
    ]
    return '{0}{2}{1}'.format(source_str, target_str, self.action)

def GraphGroup(*graphs) -> list[Graph]:
  '''
  Instantiates multiple filter graph at once.
  '''
  return [Graph(*graph) for graph in graphs if isinstance(graph, tuple)]

def alias_graph(label_from : StreamBase, label_to : str, stream_type : StreamType = StreamType.VIDEO) -> list[Graph]:
  '''
  Instantiates aliasing graph by reserving label_to from label_from.
  '''
  STREAM_FILTER = {
    StreamType.VIDEO: 'null',
    StreamType.AUDIO: 'anull',
  }

  return GraphGroup(
    ([label_from], [Label(label_to)], Action(STREAM_FILTER[stream_type])),
  )

NOT_YET_EVALUATED = object()

@dataclass(slots=True, frozen=True)
class LateExpr():
  '''
  Annotation value for Action object.
  Evaluated by VideoProcessor.
  '''
  file: str
  key: str
  _expr: Optional[str] = None
  _value: Any = field(init=False, default=NOT_YET_EVALUATED)

  @property
  def expr(self) -> str:
    if self._expr is None:
      return self.key
    return self._expr

  @property
  def evaluated(self) -> bool:
    return self._value is not NOT_YET_EVALUATED

  def __str__(self):
    return str(self._value)

del dataclass, field, KW_ONLY
del Optional, Any

__all__ = (
  'StreamType',
  'StreamSpecification',
  'StreamBase', 'Stream', 'Label',
  'Action', 'Graph', 'GraphGroup', 'alias_graph',
  'LateExpr',
)
