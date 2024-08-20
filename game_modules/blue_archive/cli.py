# ruff: noqa: F841
import argparse

from modules.shared import parser_new_game
from modules import utils

def option_mixin_group_render():
  '''
  Parser option mixin to configure video processing flow.
  '''
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
    '--intro-file',
    action='store', required=False, metavar='file',
    dest='intro_file',
    help='Video file to prepend after pipeline processing.',
  )
  parser.add_argument(
    '-t', '--team-overlay',
    action='extend', nargs='+', metavar='files',
    dest='team_overlays', type=utils.check_file,
    help='A single or set of team image for video overlay.',
  )
  parser.add_argument(
    '-o', '--output',
    action='store', required=True, metavar='file',
    dest='output_file',
    help='Output file destination to write.',
  )

  return parser

def option_mixin_set_of_files():
  '''
  Parser option mixin to receive set of input files.
  '''
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
    'files',
    action='extend', nargs=argparse.REMAINDER, type=utils.check_file,
  )

  return parser

def option_action_cutoff_detect(group_parser, *mixin_parsers):
  '''
  Option definition for Cutoff Detection.
  '''
  parser = group_parser.add_parser(
    'cutoff-detect',
    description='Prints raw state changes of given video files.',
    parents=mixin_parsers,
  )
  state_debug = parser.add_mutually_exclusive_group()
  state_debug.add_argument(
    '--state-debug',
    action='store_const', const=True, dest='cutoff_debug',
    help='Uses pre-calculated state segments.',
  )
  state_debug.add_argument(
    '--no-state-debug',
    action='store_const', const=False, dest='cutoff_debug',
    help="Don't use pre-calculated state segments if any.",
  )

def option_action_raid_merge(group_parser, *mixin_parsers):
  '''
  Option definition for Total Assault Detection.
  '''
  parser = group_parser.add_parser(
    'raid-merge',
    description='Renders Blue Archive Total Assault videos into one.',
    parents=mixin_parsers,
  )

def option_action_jfd_merge(group_parser, *mixin_parsers):
  '''
  Option definition for Joint Exercise Detection.
  '''
  parser = group_parser.add_parser(
    'jfd-merge',
    description='Renders Blue Archive Joint Firing Drill videos into one.',
    parents=mixin_parsers,
  )

  parser.add_argument(
    '--image-pos-top',
    action='store', dest='jfd_crop_top',
    default=270, type=int, metavar='pixel',
    help='Image slicing start Y-position.',
  )
  parser.add_argument(
    '--image-pos-interval',
    action='store', dest='jfd_crop_interval',
    default=137, type=int, metavar='pixel',
    help='Image slicing Y-position gap.',
  )

def define_parser(g):
  '''
  Create parser definition.
  '''
  group_parser = parser_new_game(
    'blue-archive', 'Blue Archive',
    parser_options = {
      'description': 'Set of Blue Archive video-related commands',
    }
  )

  group_render_mixin = option_mixin_group_render()
  set_files_mixin = option_mixin_set_of_files()

  option_action_cutoff_detect(group_parser, set_files_mixin)
  option_action_raid_merge(group_parser, group_render_mixin, set_files_mixin)
  option_action_jfd_merge(group_parser, group_render_mixin, set_files_mixin)

  delete = set(['define_parser'])
  delete.update(
    k
    for k in g.keys()
    if k.startswith('option_')
  )
  for delete_key in delete:
    del g[delete_key]

def fetch_action(action_name : str):
  '''
  Get module action.
  '''
  from . import action as action_module
  return getattr(action_module, action_name, None)

define_parser(globals())
