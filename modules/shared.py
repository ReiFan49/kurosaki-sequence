import argparse

parser = argparse.ArgumentParser()

def cleanup_globals(g):
  import types

  to_remove = set()
  for k, v in g.items():
    # leave reserved names
    if k[:2] == k[-2:] and k[:2] == '__' and len(k) > 4:
      continue

    conds = [
      # remove imported modules
      not isinstance(v, types.ModuleType),
      # remove "defined" functions
      not isinstance(v, types.FunctionType),
    ]

    if all(conds):
      continue
    to_remove.add(k)

  for k in to_remove:
    del g[k]

cleanup_globals(globals())

def create_subparser(g):
  import argparse
  from typing import Any
  from modules import cli as cli_extensions

  subparser = parser.add_subparsers(
    dest='game',
    parser_class=cli_extensions.SubparserExtensionParser,
  )
  def parser_new_game(
    key_name : str,
    title : str,
    *,
    key_options : dict[str, Any] = dict(),
    parser_options : dict[str, Any] = dict(),
  ):
    '''
    Defines a new parser group attached from the base subparser.
    '''
    if not isinstance(key_options, dict):
      key_options = dict()
    if not isinstance(parser_options, dict):
      parser_options = dict()

    # parser_options['parser_class'] = parser_options.get('parser_class', cli_extensions.SubparserExtensionParser)
    parser_options['parser_class'] = argparse.ArgumentParser

    game_parser = subparser.add_parser(key_name, **key_options)
    group_parser = game_parser.add_subparsers(
      title=title,
      dest='action',
      **parser_options,
    )
    return group_parser

  g['parser_new_game'] = parser_new_game
  del g['create_subparser']

create_subparser(globals())
