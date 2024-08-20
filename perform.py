#!/usr/bin/env python3
import os
import sys
import math
import json
import argparse
import logging

import task
from utils import (
  setup_logging,
  print_versions,
  noop as _noop,
  check_file as _check_file,
  set as unify_list,
)

log = logging.getLogger()
setup_logging(log)
log.setLevel(logging.DEBUG)

BLUE_ARCHIVE_INTRO_CUTOFF = 3.0
BLUE_ARCHIVE_INTRO_CUTOFF_RATE = 1.0
BLUE_ARCHIVE_GAME_CUTOFF_RATE  = 1.0

def _scan_blue_archive_points(file):
  raw_states = task.scan_video_timing(file)

  dark_states = [state for state in raw_states if state[1] in ('b', 'd')]
  split_keys = {}
  splits = []
  for i in range(len(dark_states)):
    cue = dark_states[i]
    log.debug("Cue: %r", cue)

    if 'unit_sel' not in split_keys and i + 3 <= len(dark_states):
      range_cue = dark_states[i : i+3]
      state_times, state_keys, state_values = [[x[j] for x in range_cue] for j in (0, 1, 2)]
      if state_keys == ['b', 'b', 'd'] and state_values == [True, False, False]:
        split_keys['unit_sel'] = (None, state_times[0])
        split_keys['load_on'] = (
          state_times[1],
          (state_times[1][0] + state_times[1][1], state_times[1][1])
        )
        split_keys['game_on'] = (state_times[2], None)
        continue

  for i in range(len(raw_states)):
    cue = raw_states[i]
    if cue[1] == '.':
      split_keys['game_end'] = (cue[0], None)
      continue

  return split_keys

def _determine_blue_archive_splits(*files):
  result = dict(
    (fn, _scan_blue_archive_points(fn))
    for fn in files
  )
  current_cutoff = BLUE_ARCHIVE_INTRO_CUTOFF
  for fn, timing in result.items():
    file_cutoff = timing['unit_sel'][1][0] / timing['unit_sel'][1][1]
    if file_cutoff < current_cutoff:
      current_cutoff = int(file_cutoff / BLUE_ARCHIVE_INTRO_CUTOFF_RATE) * BLUE_ARCHIVE_INTRO_CUTOFF_RATE

  for fn, timing in result.items():
    timing['unit_sel'] = (
      (
        int(timing['unit_sel'][1][0] - current_cutoff * timing['unit_sel'][1][1]),
        timing['unit_sel'][1][1],
      ),
      timing['unit_sel'][1],
    )
    timing['game_on'] = (
      timing['game_on'][0],
      (
        timing['game_on'][0][0] + math.floor(
          (timing['game_end'][0][0] - timing['game_on'][0][0]) /
          (timing['game_on'][0][1] * BLUE_ARCHIVE_GAME_CUTOFF_RATE)) * (timing['game_on'][0][1] * BLUE_ARCHIVE_GAME_CUTOFF_RATE),
        timing['game_on'][0][1]
      )
    )
    del timing['game_end']

  return {
    'results': result,
  }


def blue_archive_scan_splits(parsed):
  files = unify_list(parsed.files)
  output = json.dumps(_determine_blue_archive_splits(*files))
  print(output)

def blue_archive_merge_segments(parsed):
  video_files = parsed.files
  image_files = parsed.merge_composition or []

  for files, key in zip([image_files, video_files], ('image', 'video')):
    deduped = unify_list(files)
    assert len(files) == len(deduped), \
      'duplicate files detected on {} file list'.format(key)

  assert len(image_files) in (1, len(video_files)), \
    'expected image files either 1 or {}, given {}'.format(len(video_files), len(image_files))

  image_files[:] = image_files[:] * (len(video_files) // len(image_files))
  task.create_filter_script_raid(
    parsed.output_file,
    parsed.intro_file,
    video_files,
    image_files,
    video_splits['results']
  )

def blue_archive_merge_jfd_segments(parsed):
  video_files = parsed.files
  image_files = parsed.merge_composition or [None]
  video_splits = _determine_blue_archive_splits(*video_files)

  for files, key in zip([video_files], ('video')):
    deduped = unify_list(files)
    assert len(files) == len(deduped), \
      'duplicate files detected on {} file list'.format(key)

  task.create_filter_script_jfd(
    parsed.output_file,
    parsed.intro_file,
    video_files,
    image_files[0],
    video_splits['results']
  )

def _action_define_blue_archive(parser):
  modes = parser.add_mutually_exclusive_group()
  modes.add_argument(
    '--split', action='store_const', const=blue_archive_scan_splits, dest='callback',
    help='determine video splitting based on Blue Archive Video patterns.',
  )
  modes.add_argument(
    '--merge', action='store_const', const=blue_archive_merge_segments, dest='callback',
    help='merge videos with team composition per video',
  )
  modes.add_argument(
    '--jfd-merge', action='store_const', const=blue_archive_merge_jfd_segments, dest='callback',
    help='merge videos with team composition per video',
  )
  parser.add_argument(
    '--jfd-intro', action='store', metavar='file', dest='intro_file',
  )
  parser.add_argument(
    '--merge-composition', action='extend', nargs='+', type=_check_file, metavar='files',
    help='list of team composition overlays for the video composition',
  )
  parser.add_argument(
    '--output-file', action='store', required=True, metavar='file',
    help='output target',
  )
  parser.add_argument(
    'files', action='extend', nargs=argparse.REMAINDER, type=_check_file,
  )

def action_selection():
  result = argparse.Namespace(callback=None, files=[])
  parser = argparse.ArgumentParser()
  subparser = parser.add_subparsers()
  _action_define_blue_archive(subparser.add_parser('blue_archive'))
  parser.parse_args(namespace=result)
  #if any(not os.path.exists(f) for f in result.files):
  #  fail_files = [f for f in result.files if not os.path.exists(f)]
  #  raise ValueError('File not found. {}'.format(', '.join(fail_files)))

  if callable(result.callback):
    result.callback(result)
  else:
    parser.print_help()

if __name__ == '__main__':
  print_versions()
  action_selection()
