"""Run all tests and fail for ResourceWarnings raised during garbage collection.

Python reports destructor exceptions through unraisablehook; -W error alone
can print those exceptions without making unittest fail. Keep them visible and
also return a failing process status. No tests or warnings are skipped.
"""
import gc
from pathlib import Path
import sys
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    unraisable = []
    previous = sys.unraisablehook

    def record(event):
        unraisable.append(event.exc_type)
        previous(event)

    sys.unraisablehook = record
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', ResourceWarning)
            suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            gc.collect()
        if unraisable:
            print(f'FAILED: {len(unraisable)} unraisable resource/cleanup exceptions', file=sys.stderr)
        return 0 if result.wasSuccessful() and not unraisable else 1
    finally:
        sys.unraisablehook = previous


if __name__ == '__main__':
    sys.exit(main())
