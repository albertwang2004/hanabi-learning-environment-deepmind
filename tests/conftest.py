import os
from pathlib import Path

import pytest


def _attempt_load_pyhanabi():
  # Import locally so pytest collection does not fail before we can skip.
  from hanabi_learning_environment import pyhanabi

  pyhanabi.try_cdef()
  if pyhanabi.lib_loaded():
    return True
  if pyhanabi.try_load():
    return True

  root = Path(__file__).resolve().parents[1]
  candidates = set()
  for lib_name in ("libpyhanabi.so", "libpyhanabi.dylib"):
    candidates.update(path.parent for path in root.rglob(lib_name))
  for prefix in candidates:
    if pyhanabi.try_load(prefixes=[str(prefix)]):
      return True
  return False


@pytest.fixture(scope="session", autouse=True)
def load_pyhanabi_library():
  """Ensure the shared library is available before running any tests."""
  if not _attempt_load_pyhanabi():
    pytest.skip(
        "libpyhanabi could not be loaded; build the extension before running tests."
    )
