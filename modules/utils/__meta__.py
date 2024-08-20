def clean_modules(g):
  import types

  tr = set(k for k, v in g.items() if isinstance(v, types.ModuleType))
  for k in tr:
    del g[k]
  # del g['clean_modules']

__all__ = ()
