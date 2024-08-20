from . import utils

utils.scan_game_package(globals(), 'cli')

class GameModuleNotFound(KeyError):
  pass
class GameActionNotFound(KeyError):
  pass
class GameActionInvalid(TypeError):
  pass

def process_action(game_name : str, action_name : str, result : object):
  import types
  g = globals()

  # Modules on CLI namespace are guaranteed to be CLI Game Module
  game_mod = g.get(game_name, None)
  if not isinstance(game_mod, types.ModuleType):
    raise GameModuleNotFound(game_name)

  action = game_mod.fetch_action('execute_' + action_name)
  if action is None:
    raise GameActionNotFound(game_name, action_name)

  if not callable(action):
    raise GameActionInvalid(game_name, action_name)

  action(result)
