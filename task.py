import os
import math
import time
import contextlib
import functools
import subprocess

import numpy as np
import cv2 as cv

DARK_VALUE_THRESHOLD = 5
DARK_DOMINANCE_THRESHOLD = 70
DARK_COMPLETE_THRESHOLD = 95

@contextlib.contextmanager
def _open_video_file(file):
  video = cv.VideoCapture(file)

  try:
    yield video
  finally:
    video.release()

def scan_video_timing(file):
  def create_rectangle_mask(frame, offset, color):
    mask = np.full(frame.shape[:2], 255, dtype='uint8')
    cv.rectangle(
      mask,
      (offset, offset),
      (frame.shape[0] - offset, frame.shape[1] - offset),
      color,
      -1,
    )
    return mask

  states = []

  with _open_video_file(file) as video:
    loading_mask = None

    n = 0
    fps = video.get(cv.CAP_PROP_FPS)
    last_state = ()

    while video.isOpened():
      ret, frame = video.read()
      if not ret:
        break

      n_fr = (n, fps)

      if loading_mask is None:
        loading_mask = create_rectangle_mask(frame, 80, 0)

      gray_frame = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
      gray_hist  = cv.calcHist([gray_frame], [0], loading_mask, [256], [0, 256])

      total_dark_pixels = gray_hist[:DARK_VALUE_THRESHOLD].sum()
      ratio_dark_pixels = total_dark_pixels / gray_hist.sum()
      is_gray_dark  = ratio_dark_pixels * 100 >= DARK_DOMINANCE_THRESHOLD
      is_gray_black = ratio_dark_pixels * 100 >= DARK_COMPLETE_THRESHOLD

      if not last_state:
        last_state = (is_gray_dark, is_gray_black)

      if last_state[1] != is_gray_black:
        states.append((n_fr, 'b', is_gray_black))
      elif last_state[0] != is_gray_dark:
        states.append((n_fr, 'd', is_gray_dark))

      last_state = (is_gray_dark, is_gray_black)
      n += 1

  states.append(((n, fps), '.', None))

  return states

def _create_filter_segments(video_files):
  segs = [None]
  segs[1:] = [fn for fn in video_files for i in range(3)]
  segs[len(segs):] = [None] * (
    math.ceil(len(segs) / 10) * 10 - len(segs)
  )
  return segs

def create_filter_script_jfd(output_file, intro_file, video_files, image_file, video_splits):
  raw_segments = _create_filter_segments(video_files)
  raw_segments.append(intro_file)
  raw_segments.append(image_file)

  file_indices = {}
  for file in [*video_files, intro_file, image_file]:
    if file is None:
      continue
    file_indices[file] = raw_segments.index(file)

  input_segments = []
  for i, raw_segment in zip(range(len(raw_segments)), raw_segments):
    if raw_segment is None:
      if i == 0:
        input_segments.append({'f': 'lavfi', 'i': 'color=c=black:s=1600x900:r=60'})
      else:
        input_segments.append({'f': 'lavfi', 'i': 'nullsrc'})
      continue

    if raw_segment in video_splits:
      split = video_splits[raw_segment]
      key = list(split)[(i - 1) % len(split)]
      data = split[key]
      input_segments.append({
        'ss': round(data[0][0] / data[0][1], 3),
        'to': round(data[1][0] / data[1][1], 3),
         'i': raw_segment,
      })
      continue

    input_segments.append({'i': raw_segment})

  # initialize filters
  filter_commands = []
  if image_file is not None:
    image_index = file_indices[image_file]
    for i in range(len(video_files)):
      i += 1
      filter_commands.append([(
        [(image_index, 'v')], [f'i{i}'],
        f'crop=1392:135:(iw-ow)/2:{270+137*(i-1)}'
      )])

  # handle per-video filters
  filter_video_base = {}
  for n, video in zip(range(len(video_files)), video_files):
    n += 1
    commands = []
    video_index = file_indices[video]

    commands.append([(
      [(video_index + i, j) for i in range(3) for j in ('v', 'a')],
      [f'r{j}p{n}_0' for j in ('v', 'a')],
      'concat=n=3:v=1:a=1'
    )])
    commands.append([
      ([f'rvp{n}_0'], [], 'scale=1600:-1',),
      ([(0, 'v')], [f'rvp{n}_1'], 'overlay=x=(W-w)/2:y=H-h:eof_action=endall:shortest=1'),
    ])
    if image_file is not None:
      commands.append([(
        [f'rvp{n}_1', f'i{n}'], [f'rvp{n}_2'],
        'overlay=x=(W-w)/2:y=0'
      )])
    else:
      commands.append([
        ([f'rvp{n}_1'], [f'rvp{n}_2'], 'split'),
        ([], [], 'nullsink'),
      ])

    filter_video_base[video] = commands
    filter_commands.extend(commands)

  # filter_commands.extend(filter_video_base.values())

  # aggregate filters
  audio_max_edit, video_max_edit = 0, 2
  fade_duration = 0.5
  reverse_fade_index = zip(range(len(video_files) - 1, 0, -1), [len(video_files)] + [None] * len(video_files))
  filter_fade_commands = {'v': [], 'a': []}
  for source_index, target_index in reverse_fade_index:
    source_labels = [source_index]
    if target_index is not None:
      source_labels.append(target_index)

    source_video = video_files[source_index - 1]
    source_splits = video_splits[source_video]
    source_duration = round(
      functools.reduce(
        lambda x, y: x + (y[1][0] - y[0][0]) / y[1][1],
        (split for split in source_splits.values()), 0
      ), 3
    )

    source_a_labels, source_v_labels = tuple(
      [f'r{x}p{i}_{y}' for i in source_labels]
      if y is not None
      else []
      for x, y in (('a', audio_max_edit), ('v', video_max_edit))
    )

    if source_v_labels:
      filter_fade_commands['v'].append((source_v_labels, [], f'xfade=fade:{fade_duration}:{source_duration - fade_duration}'))
    if source_a_labels:
      filter_fade_commands['a'].append((source_a_labels, [], f'acrossfade=d={fade_duration}'))

  if intro_file is not None:
    intro_index = file_indices[intro_file]
    filter_commands.append([
      ([(intro_index, 'v')], [f'rvpi_0'], 'scale=1600:-1')
    ])
    filter_fade_commands['v'].append(([f'rvpi_0'], ['vout'], 'concat=n=2:v=1:a=0'))
    filter_fade_commands['a'].append(([(intro_index, 'a')], ['aout'], 'concat=n=2:v=0:a=1'))
  else:
    filter_fade_commands['v'][-1][1].append('vout')
    filter_fade_commands['a'][-1][1].append('aout')

  for j in ('v', 'a'):
    filter_commands.append(filter_fade_commands[j])

  fn = os.path.join('/tmp', 'filter.{}.filter_complex').format(
    int(time.time() * 1000),
  )

  try:
    _write_commands(fn, filter_commands)
    ffmpeg_args = ['ffmpeg', '-y', '-stats', '-loglevel', '24']
    for input_segment in input_segments:
      ffmpeg_args.extend(str(arg) for k, v in input_segment.items() for arg in (f'-{k}', v))
    ffmpeg_args.extend(['-filter_complex_script', fn])
    ffmpeg_args.extend(['-threads', '1', '-filter_threads', '1'])
    ffmpeg_args.extend(['-r', '60', '-b:v', '4M'])
    ffmpeg_args.extend(['-map', '[vout]', '-map', '[aout]', output_file])

    subprocess.run(ffmpeg_args, check=True)
  finally:
    if os.path.exists(fn):
      os.unlink(fn)

def _write_commands(fn, filter_commands):
  command_list = []
  for command_set in filter_commands:
    command_group = []
    for sources, targets, command in command_set:
      ss, st = [
        ''.join(
          f'[{label[0]}:{label[1]}]' if isinstance(label, tuple)
          else f'[{label}]'
          for label in labels
        ) for labels in (sources, targets)
      ]
      command_group.append('{0}{2}{1}'.format(ss, st, command))
    command_list.append(',\n'.join(command_group))

  command_lines = ';\n'.join(command_list).splitlines()
  with open(fn, 'w') as f:
    for line in command_lines:
      f.write(line + '\n')
