#!/usr/bin/env python3
# ruff: noqa: D103
import logging
import argparse

from modules.utils import (
  setup_logging,
  print_versions,
)
from modules import debug_flags

from game_modules import cli

log = logging.getLogger()
setup_logging(log)

if debug_flags.DEBUG_LOGGING:
  log.setLevel(logging.DEBUG)

def action_selection():
  from modules.shared import parser
  def underscore(s):
    return s.replace('-', '_') if isinstance(s, str) else None

  result = argparse.Namespace(game=None, action=None, files=[])
  parser.parse_args(namespace=result)
  #if any(not os.path.exists(f) for f in result.files):
  #  fail_files = [f for f in result.files if not os.path.exists(f)]
  #  raise ValueError('File not found. {}'.format(', '.join(fail_files)))

  filtered_result = argparse.Namespace(**{
    k: v for k, v in vars(result).items()
    if k not in ('game', 'action')
  })
  # del filtered_result.game, filtered_result.action

  try:
    cli.process_action(underscore(result.game), underscore(result.action), filtered_result)
  except (cli.GameActionNotFound, cli.GameActionInvalid):
    log.error('Action %s on module %s not found', result.action, result.game)
    game_parser = next(
      group.choices[result.game]
      for group in parser._subparsers._group_actions
      if group.dest == 'game'
    )
    game_parser.print_help()
  except cli.GameModuleNotFound:
    log.error('Module %s not found', result.game)
    parser.print_help()

if __name__ == '__main__':
  print_versions()
  action_selection()
