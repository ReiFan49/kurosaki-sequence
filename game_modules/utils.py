def scan_game_package(g, mod):
  '''
  Scan CLI packages of each game modules.
  '''
  assert g['__package__'] == __package__, f"Only for {__package__} module."

  import os
  import glob
  import types
  import importlib

  dirname = os.path.dirname(g['__file__'])
  for pkg_file in glob.iglob(f'*/{mod}.py', root_dir = dirname):
    module_pkg = os.path.dirname(pkg_file)
    module = importlib.import_module(f'.{module_pkg}.{mod}', package=__package__)
    # Link shortcut of given package
    g[module_pkg] = module

  util_keys = set(
    k
    for k, v in g.items()
    if isinstance(v, types.ModuleType) and \
      v.__file__ == __file__
  )

  for k in util_keys:
    del g[k]
