'''
CLI extension module.

This module provides extra capability of ArgumentParser.
'''

import argparse

def describe_choice(self, choice_name : str, parser) -> str:
  '''
  Describe choice and it's description.
  '''
  parts = []

  extra_pad = self._action_max_length - len(choice_name)

  if parser.description.strip():
    parts.append('%*s%s%*s%s\n' % (
      self._current_indent, '', choice_name,
      extra_pad, '', parser.description.strip(),
    ))
  else:
    parts.append('%*s%s\n' % (self._current_indent, '', choice_name))

  return self._join_parts(parts)

def describe_subparser_choice(self, action):
  '''
  Format SubparserAction to list all the choices vertically instead.
  '''
  if action.help is argparse.SUPPRESS:
    return

  choices = [choice for choice in action.choices]
  max_length = max(map(len, choices)) + self._current_indent
  self._action_max_length = max(
    self._action_max_length,
    max_length,
  )

  for choice_name, choice in action.choices.items():
    self._add_item(describe_choice, [self, choice_name, choice])

class SubparserDescribeMixin():
  def format_help(self):
    formatter = self._get_formatter()

    formatter.add_usage(
      self.usage, self._actions,
      self._mutually_exclusive_groups,
    )
    formatter.add_text(self.description)

    for action_group in self._action_groups:
      formatter.start_section(action_group.title)
      formatter.add_text(self.description)
      for action in action_group._group_actions:
        if isinstance(action, argparse._SubParsersAction):
          describe_subparser_choice(formatter, action)
        else:
          formatter.add_argument(action)
      formatter.end_section()
    formatter.add_text(self.epilog)

    return formatter.format_help()

class SubparserExtensionParser(SubparserDescribeMixin, argparse.ArgumentParser):
  pass
