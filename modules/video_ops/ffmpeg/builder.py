import os, sys # noqa: F401
import json
import time
import functools
import subprocess
import logging
from enum import Enum
from typing import Any

from modules.video_ops import data, base
from .stream import *
from . import utils

log = logging.getLogger(__name__)

def supports_feedback_filter() -> bool:
  '''
  Method to check FFMPEG to support Feedback filter or not.
  '''
  return utils.FFMPEG_VERSION >= (5, 1)

class VideoTransform(base.VideoTransform):
  def process(self):
    vp = VideoProcessor(self)
    vp.init_image_filters()
    vp.init_video_filters()
    vp.aggregate_streams(
      audio_max_edit = 0,
      video_max_edit = 2,
      fade_duration = 0.5,
    )
    vp.prepend_intro()
    vp.append_fade_commands()
    vp.ensure_sink_out()
    vp.execute_ffmpeg_commands()

  def assign_specifications(self):
    '''
    Load up FFMPEG compliant variables to specification object.
    '''
    self.stream_specifications = {}

    for video_file in self.video_files:
      process = subprocess.run([
        'ffprobe',
        '-loglevel', '16',
        '-select_streams', 'v',
        '-print_format', 'json',
        '-show_streams', video_file,
      ], check=True, capture_output=True, text=True)

      video_streams = []
      self.stream_specifications[video_file] = None

      for raw_spec in json.loads(process.stdout).get('streams', []):
        filter_spec = {k: v for k, v in raw_spec.items() if k in StreamSpecification.__slots__}
        stream_spec = StreamSpecification(**filter_spec)
        video_streams.append(stream_spec)

      if video_streams:
        self.stream_specifications[video_file] = video_streams[0]

class VideoProcessor(base.VideoProcessor):
  '''
  Video Processing module for FFMPEG.
  '''
  def __init__(self, tf: VideoTransform):
    super().__init__(tf)

    self.renders : list[dict[str, Any]] = []
    self.filters : list[list[Graph]] = []
    self.fade_commands : dict[StreamType, list[Graph]] = {}

    self.translate_renders()

  def translate_renders(self):
    '''
    Translate render instruction set to compatible with FFMPEG.
    '''
    renders = []
    for render in self.tf.renders:
      if isinstance(render, data.RenderSpecial):
        if isinstance(render, data.RenderIgnore):
          renders.append({'f': 'lavfi', 'i': Action('nullsrc')})
        elif isinstance(render, data.RenderColorScreen):
          renders.append({
            'f': 'lavfi',
            'i': Action('color', params={
              'c': render.color,
              's': '{0.width}x{0.height}'.format(render),
              'r': render.fps,
            }),
          })
        else:
          renders.append({'f': 'lavfi', 'i': Action('nullsrc')})
      elif isinstance(render, data.RenderStatic):
        renders.append({'r': 60, 'i': render.file})
      elif isinstance(render, data.RenderVideo):
        renders.append({
          'ss': render.start_time,
          'to': render.end_time,
          'i': render.file,
        })
      else:
        raise TypeError(f'unsupported render object ({type(render)})')
    self.renders = renders

  def init_image_filters(self):
    '''
    Initialize image filters.
    '''
    commands = []
    if self.tf.image_files:
      for i in range(len(self.tf.video_files)):
        image = self.tf.image_files[i % len(self.tf.image_files)]
        image_index = self.tf.indices[image]
        if self.tf.options.get('image_crop', False):
          commands.append(GraphGroup(
            (
              [Stream(image_index, StreamType.VIDEO)],
              [Label(f'i{i + 1}')],
              Action('crop', args=[
                self.tf.options['image_crop_width'],
                self.tf.options['image_crop_height'],
                '(iw-ow)/2',
                self.tf.options['image_crop_start'] + self.tf.options['image_crop_interval'] * i,
              ]),
            ),
          ))
        else:
          commands.append(GraphGroup(
            (
              [Stream(image_index, StreamType.VIDEO)],
              [Label(f'i{i + 1}')],
              Action('scale', args=[-1, 162]),
            ),
          ))

    self.filters.extend(commands)

  def init_video_filters(self):
    '''
    Initialize video filters.
    '''
    self.init_video_combined_segments()

    for i, video in enumerate(self.tf.video_files):
      n = i + 1
      commands = []
      video_index = self.tf.indices[video]
      image = self.tf.image_files[n % len(self.tf.image_files)] if self.tf.image_files else None
      segments = self.tf.file_segments[video]
      special_segments = segments - {1, 2}

      # combine the spliced parts
      source_streams = [Stream(video_index + i, s) for i in range(3) for s in StreamType]

      if len(special_segments) > 1:
        source_streams[4:6] = [Label(f'r{s}c{n}_splice') for i in (2,) for s in StreamType]

      is_blur_header = True
      if is_blur_header:
        blur_data = {
          'crop_width': 0.46,
          'crop_left': 0.375,
          'color_key_action': Action('colorkey', args=['0x000020', 0.9, 0]),
          'geq_rgb': {c: f'if(lt(alpha(X\,Y)\,16)\, {c}(W/2\,0)\, {c}(X\,Y))' for c in ('r', 'g', 'b')},
          'geq_action': Action('geq', params={}),
        }
        blur_data['geq_action'].params.update(blur_data['geq_rgb'])
        blur_data['geq_action'].params.update({'a': 255})

        if supports_feedback_filter():
          commands.append(GraphGroup(
            (
              [Stream(video_index + 0, StreamType.VIDEO), Label(f'fvp{n}_1')],
              [Label(f'fvp{n}_1')],
              Action('feedback@feedback_action', args=[
                LateExpr(video, 'width', f'int(width * {blur_data["crop_left"]})'), 0,
                LateExpr(video, 'width', f'int(width * {blur_data["crop_width"]})'), 60,
              ]),
            ),
            ([], [Label(f'fvp{n}_1')], blur_data['color_key_action']),
            ([Label(f'fvp{n}_1')], [Label(f'rvpp{n}_blur')], blur_data['geq_action']),
          ))
        else:
          commands.append(GraphGroup(
            (
              [Stream(video_index + 0, StreamType.VIDEO)], [],
              Action('crop@feedback_piece_crop', args=[
                f'iw * {blur_data["crop_width"]}', 60,
                f'iw * {blur_data["crop_left"]}', 0,
              ]),
            ),
            ([], [], blur_data['color_key_action']),
            ([], [], blur_data['geq_action']),
            ([], [], Action('setpts', args=['PTS-STARTPTS'])),
            (
              [Stream(video_index + 0, StreamType.VIDEO)], [Label(f'rvpp{n}_blur')],
              Action('overlay@feedback_piece_overlay', args=[f"W * {blur_data['crop_left']}", 0]),
            ),
            # ([], [Label(f'rvpp{n}_blur')], blur_data['geq_action']),
          ))

        source_streams[0] = Label(f'rvpp{n}_blur')

      commands.append(GraphGroup(
        (
          source_streams,
          [Label(f'r{s}p{n}_0') for s in StreamType],
          Action('concat', args=[3, 1, 1]),
        ),
      ))

      # scale and place video
      commands.append(GraphGroup(
        ([Label(f'rvp{n}_0')], [], Action('scale', args=[1600, -1])),
        ([], [], Action('setpts', args=['PTS-STARTPTS'])),
        (
          [Stream(0, StreamType.VIDEO)], [Label(f'rvp{n}_1')],
          Action('overlay', params={
            'x': '(W-w)/2',
            'y': 'H-h',
            'eof_action': 'endall',
            'shortest': 1,
          }),
        ),
      ))

      # place image overlay if any
      if image is not None:
        commands.append(GraphGroup(
          (
            [Label(f'rvp{n}_1'), Label(f'i{n}')], [Label(f'rvp{n}_2')],
            Action('overlay', params={'x': '(W-w)/2', 'y': 0}),
          ),
        ))
      else:
        commands.append(alias_graph(Label(f'rvp{n}_2'), f'rvp{n}_2'))

      self.filters.extend(commands)
    pass

  def init_video_combined_segments(
    self,
    *,
    fade_duration: float = 0.5,
  ):
    '''
    Initialize special spliced segments.

    Performs quick crossfade with given special segments.
    '''
    for i, video in enumerate(self.tf.video_files):
      initial_fade_commands : dict[StreamType, list[Graph]] = {s: [] for s in StreamType}
      video_index = self.tf.indices[video]
      segments = self.tf.file_segments[video]
      splits = self.tf.splits[video]
      special_segments = segments - {1, 2}

      if len(special_segments) <= 1:
        continue

      map_segments : dict[int, Enum] = {
        k.value: k
        for k in splits
        if k.value in special_segments
      }
      special_indices = sorted(special_segments)
      reverse_fade_index = zip(
        special_indices[-2::-1],
        [special_indices[-1]] + [None] * len(special_indices),
      )

      for source_index, target_index in reverse_fade_index:
        source_labels = [source_index]
        if target_index is not None:
          source_labels.append(target_index)

        segment_key = map_segments[source_index]
        source_time = splits[segment_key]
        source_duration = round(float(source_time.duration), 3)

        source_v_labels, source_a_labels = tuple(
          [Stream(video_index + (i - 1), s) for i in source_labels]
          for s in StreamType
        )

        if source_v_labels:
          initial_fade_commands[StreamType.VIDEO].append(Graph(
            source_v_labels, [],
            Action('xfade', args=['fade', fade_duration, source_duration - fade_duration]),
          ))
        if source_a_labels:
          initial_fade_commands[StreamType.AUDIO].append(Graph(
            source_a_labels, [],
            Action('acrossfade', params={'d': fade_duration}),
          ))

      for s, stream_commands in initial_fade_commands.items():
        stream_commands[-1].targets.append(Label(f'r{s}c{i+1}_splice'))
        self.filters.append(stream_commands)

  def aggregate_streams(
    self,
    *,
    video_max_edit: int = 2,
    audio_max_edit: int = 0,
    fade_duration:  float = 0.5,
  ):
    '''
    Aggregate all video files using fade transition.
    '''
    reverse_fade_index = zip(
      range(len(self.tf.video_files) - 1, 0, -1),
      [len(self.tf.video_files)] + [None] * len(self.tf.video_files),
    )
    fade_commands : dict[StreamType, list[Graph]] = dict((s, []) for s in StreamType)
    for source_index, target_index in reverse_fade_index:
      source_labels = [source_index]
      if target_index is not None:
        source_labels.append(target_index)

      source_video = self.tf.video_files[source_index - 1]
      source_splits = self.tf.splits[source_video]
      source_index_segments = self.tf.file_segments[source_video]
      source_special_segments = source_index_segments - {1, 2}
      source_duration = round(
        functools.reduce(
          lambda x, y: x + float(y.duration),
          (split for split in source_splits.values()), 0.0,
        ), 3,
      ) - (len(source_special_segments) - 1) * fade_duration

      source_v_labels, source_a_labels = tuple(
        [Label(f'r{s}p{i}_{y}') for i in source_labels]
        if y is not None else []
        for s, y in zip(StreamType, (video_max_edit, audio_max_edit))
      )

      if source_v_labels:
        fade_commands[StreamType.VIDEO].append(Graph(
          source_v_labels, [],
          Action('xfade', args=['fade', fade_duration, source_duration - fade_duration]),
        ))
      if source_a_labels:
        fade_commands[StreamType.AUDIO].append(Graph(
          source_a_labels, [],
          Action('acrossfade', params={'d': fade_duration}),
        ))

    self.fade_commands = fade_commands

  def prepend_intro(self):
    '''
    Prepend intro to the video sequence, if any.
    '''
    if self.tf.intro_file is not None:
      intro_index = self.tf.indices[self.tf.intro_file]
      self.filters.append(GraphGroup(
        ([Stream(intro_index, 'v')], [Label('rvpi_0')], Action('scale', args=[1600, -1])),
      ))
      self.fade_commands[StreamType.VIDEO].append(
        Graph([Label('rvpi_0')], [Label('vout')], Action('concat', args=[2, 1, 0])),
      )
      self.fade_commands[StreamType.AUDIO].append(
        Graph([Stream(intro_index, 'a')], [Label('aout')], Action('concat', args=[2, 0, 1])),
      )
    else:
      if len(self.fade_commands[StreamType.VIDEO]) > 0:
        self.fade_commands[StreamType.VIDEO][-1].targets.append(Label('vout'))
      if len(self.fade_commands[StreamType.AUDIO]) > 0:
        self.fade_commands[StreamType.AUDIO][-1].targets.append(Label('aout'))

  def append_fade_commands(self):
    '''
    Combines Fade Commands into main pipeline.
    '''
    for s in StreamType:
      if self.fade_commands[s]:
        self.filters.append(self.fade_commands[s])

  def ensure_sink_out(self):
    '''
    Assures output sinks existed.
    '''
    have_out = set()
    for graph_group in self.filters:
      for graph in graph_group:
        for stream in StreamType:
          if Label(stream + 'out') not in graph.targets:
            continue

          have_out.add(stream)

    if have_out == set(StreamType):
      return

    last_label = {}
    for graph_group in self.filters:
      for graph in graph_group:
        for stream in StreamType:
          if stream in have_out:
            continue

          for target in graph.targets:
            if target.name[:3] != f'r{stream}p':
              continue
            last_label[stream] = target

    for stream, label in last_label.items():
      self.filters.append(alias_graph(label, stream + 'out', stream))

  def evaluate_expressions(self):
    '''
    Evaluate late expressions.
    '''
    action_list = []
    action_list.extend(render['i'] for render in self.renders if isinstance(render['i'], Action))
    action_list.extend(graph.action for graph_group in self.filters for graph in graph_group)
    action_list[:] = [action for action in action_list if action.late_evaluation]
    if not action_list:
      return
    log.warning("Found %d action(s) containing Late Expressions.", len(action_list))

    expressions = set()
    for action in action_list:
      expressions.update(expr for args in (action.args, action.params.values()) for expr in args if isinstance(expr, LateExpr))

    if expressions:
      log.warning("Found %d Late Expression(s).", len(expressions))

    for expr in expressions:
      spec = self.tf.stream_specifications[expr.file]
      scope_dict = {k: getattr(spec, k) for k in spec.__slots__ if hasattr(spec, k)}
      result = eval(expr.expr, {}, scope_dict)
      object.__setattr__(expr, '_value', result)

  def write_ffmpeg_commands(self, fn):
    '''
    Write FFMPEG commands to file.
    '''
    command_list = [
      ',\n  '.join(
        str(graph)
        for graph in command_graph
      )
      for command_graph in self.filters
    ]

    command_lines = ';\n'.join(command_list).splitlines()
    with open(fn, 'w') as f:
      for line in command_lines:
        f.write(line + '\n')

  def execute_ffmpeg_commands(self):
    '''
    Execute FFMPEG commands.
    '''
    fn = os.path.join('/tmp', 'filter.{}.filter_complex').format(int(time.time() * 1000))
    try:
      self.evaluate_expressions()
      self.write_ffmpeg_commands(fn)
      ffmpeg_args = ['ffmpeg', '-y',  '-stats', '-hide_banner']
      ffmpeg_args.extend(['-loglevel', '24'])
      # ffmpeg_args.extend(['-loglevel', '40'])
      for render in self.renders:
        ffmpeg_args.extend(str(arg) for k, v in render.items() for arg in (f'-{k}', v))
      ffmpeg_args.extend(['-filter_complex_script', fn])
      ffmpeg_args.extend(['-r', '60', '-b:v', '4M'])
      # ffmpeg_args.extend(['-t', '5.0'])
      ffmpeg_args.extend(['-map', '[vout]', '-map', '[aout]', self.tf.output_file])

      log.debug("Running FFMPEG with arguments:")
      log.debug("%s", ' '.join(ffmpeg_args[1:]))

      subprocess.run(ffmpeg_args, check=True)
    finally:
      if os.path.exists(fn):
        # log.info('Filter content:\n%s', open(fn).read())
        os.unlink(fn)

__all__ = (
  'VideoTransform',
  'VideoProcessor',
)
