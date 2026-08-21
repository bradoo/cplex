import os
import unittest
from pathlib import Path


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
