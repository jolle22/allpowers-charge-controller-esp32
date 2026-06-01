"""
Tests for main.py — is_within_awake_time and get_seconds_till_wake.

MicroPython-specific modules are stubbed so these tests run under
standard CPython (pytest / unittest).
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub MicroPython modules before importing main
# ---------------------------------------------------------------------------

def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod

# uasyncio
_stub_module("uasyncio")

# machine
_machine = _stub_module(
    "machine",
    Pin=MagicMock,
    deepsleep=MagicMock(),
    reset_cause=MagicMock(return_value=0),
    DEEPSLEEP_RESET=1,
)

# wifi (not part of this repo — stub it)
_stub_module("wifi", wifi_connect=MagicMock())

# dtu (hoymiles-wifi DTU client)
_stub_module("dtu", DTU=MagicMock())

# Redirect the local logging.py so basicConfig doesn't write files
_logging_stub = _stub_module(
    "logging",
    basicConfig=MagicMock(),
    info=MagicMock(),
    warning=MagicMock(),
    error=MagicMock(),
    debug=MagicMock(),
    DEBUG=10,
)

# charge_controller depends on the same stubs — import it first so the
# module object is cached before main.py imports it
import importlib

# Make sure charge_controller can be imported
sys.modules.pop("charge_controller", None)
import charge_controller  # noqa: E402 (needed after stubs)

sys.modules.pop("main", None)
import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Cfg:
    """Minimal Config-alike for passing into the pure functions."""
    def __init__(self, start_time=8, end_time=17):
        self.start_time = start_time
        self.end_time = end_time


def _make_localtime(hour, minute=0):
    """Return a tuple shaped like time.localtime() with the given h:m."""
    # (year, month, mday, hour, minute, second, weekday, yearday)
    return (2024, 1, 1, hour, minute, 0, 0, 1)


# ---------------------------------------------------------------------------
# Tests for is_within_awake_time
# ---------------------------------------------------------------------------

class TestIsWithinAwakeTime(unittest.TestCase):

    def _call(self, hour, minute, start=8, end=17):
        cfg = _Cfg(start_time=start, end_time=end)
        with patch("time.localtime", return_value=_make_localtime(hour, minute)):
            return main.is_within_awake_time(cfg)

    # --- inside window ---

    def test_midday_is_awake(self):
        self.assertTrue(self._call(12, 0))

    def test_just_after_start_is_awake(self):
        # 08:01 — one minute after start
        self.assertTrue(self._call(8, 1))

    def test_just_before_end_is_awake(self):
        # 16:59 — one minute before end
        self.assertTrue(self._call(16, 59))

    # --- boundary: start ---

    def test_exactly_at_start_is_not_awake(self):
        # current == start * 60 → condition is strict ">"
        self.assertFalse(self._call(8, 0))

    # --- boundary: end ---

    def test_exactly_at_end_is_not_awake(self):
        # current == end * 60 → condition is strict "<"
        self.assertFalse(self._call(17, 0))

    # --- outside window ---

    def test_before_start_is_not_awake(self):
        self.assertFalse(self._call(7, 59))

    def test_after_end_is_not_awake(self):
        self.assertFalse(self._call(17, 1))

    def test_midnight_is_not_awake(self):
        self.assertFalse(self._call(0, 0))

    # --- custom window ---

    def test_custom_window_inside(self):
        self.assertTrue(self._call(10, 30, start=9, end=20))

    def test_custom_window_outside(self):
        self.assertFalse(self._call(8, 0, start=9, end=20))


# ---------------------------------------------------------------------------
# Tests for get_seconds_till_wake
# ---------------------------------------------------------------------------

class TestGetSecondsTillWake(unittest.TestCase):

    def _call(self, hour, minute, start=8):
        cfg = _Cfg(start_time=start)
        with patch("time.localtime", return_value=_make_localtime(hour, minute)):
            return main.get_seconds_till_wake(cfg)

    def test_one_minute_before_wake_returns_60_seconds(self):
        # current = 07:59, wake = 08:00 → 1 minute → 60 s
        self.assertEqual(self._call(7, 59), 60)

    def test_two_hours_before_wake(self):
        # 06:00 → 08:00 = 120 min → 7200 s
        self.assertEqual(self._call(6, 0), 7_200)

    def test_exactly_at_wake_time_returns_zero_or_full_day(self):
        # current == wake_minutes → (0) % (24*60) == 0 → 0 seconds
        self.assertEqual(self._call(8, 0), 0)

    def test_just_past_wake_wraps_to_next_day(self):
        # 08:01, wake=08:00 → 1439 min till next wake → 86340 s
        self.assertEqual(self._call(8, 1), (24 * 60 - 1) * 60)

    def test_midnight_to_default_wake(self):
        # 00:00 → 08:00 = 480 min → 28800 s
        self.assertEqual(self._call(0, 0), 28_800)

    def test_result_is_in_seconds(self):
        seconds = self._call(6, 0, start=7)
        # 60 min → 3600 s
        self.assertEqual(seconds, 3_600)

    def test_custom_start_time(self):
        # current 05:00, wake 06:30 → 90 min → 5400 s
        self.assertEqual(self._call(5, 0, start=6), 3_600)


if __name__ == "__main__":
    unittest.main()
