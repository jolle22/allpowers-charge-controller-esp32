"""
conftest.py — lives in tests/, pytest is invoked from tests/.

Adds the project root to sys.path so test modules can import
charge_controller.py and main.py, while keeping the project root's
MicroPython logging.py out of the way (it is not on sys.path when
pytest starts from the tests/ directory).
"""

import sys
import os

# Project root is one level up from this conftest.
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
