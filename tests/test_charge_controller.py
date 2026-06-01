"""
Tests for charge_controller.py — ChargeController class.

MicroPython-specific modules (machine, uasyncio, dtu, logging) are stubbed
so tests run under standard CPython (pytest / unittest).
"""

import sys
import types
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

# ---------------------------------------------------------------------------
# Stub MicroPython modules
# ---------------------------------------------------------------------------

def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# uasyncio → just alias stdlib asyncio so async/await works
sys.modules["uasyncio"] = asyncio

# machine.Pin — track value() calls
_pin_instance = MagicMock()
_MockPin = MagicMock(return_value=_pin_instance)
_MockPin.OUT = 1
_stub_module("machine", Pin=_MockPin)

# logging stub
_logging = _stub_module(
    "logging",
    basicConfig=MagicMock(),
    info=MagicMock(),
    warning=MagicMock(),
    error=MagicMock(),
    debug=MagicMock(),
    DEBUG=10,
)

# DTU stub — default get_real_data_new returns None (no response)
_mock_dtu_instance = MagicMock()
_mock_dtu_instance.get_real_data_new = AsyncMock(return_value=None)
_MockDTU = MagicMock(return_value=_mock_dtu_instance)
_stub_module("dtu", DTU=_MockDTU)

# Now import the module under test
sys.modules.pop("charge_controller", None)
import charge_controller  # noqa: E402
from charge_controller import ChargeController, RELAY_PIN_NUMBER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in the test event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_controller(threshold_watts=260, *, reset_mocks=True):
    """Create a ChargeController with a fresh DTU mock."""
    if reset_mocks:
        _pin_instance.reset_mock()
        _mock_dtu_instance.reset_mock()
        _mock_dtu_instance.get_real_data_new = AsyncMock(return_value=None)
    return ChargeController("192.168.0.1", threshold_watts)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def setUp(self):
        self.cc = _make_controller(threshold_watts=260)

    def test_dtu_created_with_correct_ip(self):
        _MockDTU.assert_called_with("192.168.0.1", is_encrypted=False, enc_rand=b"")

    def test_threshold_stored_in_tenths_of_watts(self):
        self.assertEqual(self.cc._threshold_x10, 260 * 10)

    def test_relay_pin_created_on_correct_gpio(self):
        _MockPin.assert_called_with(RELAY_PIN_NUMBER, _MockPin.OUT)

    def test_relay_high_after_init(self):
        # stop_charging() called in __init__ → pin value(1)
        _pin_instance.value.assert_called_with(1)

    def test_is_charging_false_after_init(self):
        self.assertFalse(self.cc.is_charging)


# ---------------------------------------------------------------------------
# start_charging / stop_charging
# ---------------------------------------------------------------------------

class TestRelayHelpers(unittest.TestCase):

    def setUp(self):
        self.cc = _make_controller()

    def test_start_charging_sets_is_charging_true(self):
        self.cc.start_charging()
        self.assertTrue(self.cc.is_charging)

    def test_start_charging_drives_pin_low(self):
        self.cc.start_charging()
        self.cc.relay_pin.value.assert_called_with(0)

    def test_stop_charging_sets_is_charging_false(self):
        self.cc.start_charging()
        self.cc.stop_charging()
        self.assertFalse(self.cc.is_charging)

    def test_stop_charging_drives_pin_high(self):
        self.cc.start_charging()
        _pin_instance.reset_mock()
        self.cc.stop_charging()
        self.cc.relay_pin.value.assert_called_with(1)

    def test_idempotent_start(self):
        self.cc.start_charging()
        self.cc.start_charging()
        self.assertTrue(self.cc.is_charging)

    def test_idempotent_stop(self):
        self.cc.stop_charging()
        self.cc.stop_charging()
        self.assertFalse(self.cc.is_charging)


# ---------------------------------------------------------------------------
# control_charging — no DTU response
# ---------------------------------------------------------------------------

class TestControlChargingNoDTUResponse(unittest.TestCase):

    def test_returns_without_changing_relay_when_dtu_returns_none(self):
        cc = _make_controller()
        _mock_dtu_instance.get_real_data_new = AsyncMock(return_value=None)
        _pin_instance.reset_mock()
        _run(cc.control_charging())
        # No relay change after initialisation call
        _pin_instance.value.assert_not_called()


# ---------------------------------------------------------------------------
# control_charging — sgs entries (normal path)
# ---------------------------------------------------------------------------

class TestControlChargingWithSgs(unittest.TestCase):

    def _data(self, *active_powers):
        return {"sgs": [{"active_power": p} for p in active_powers]}

    def test_above_threshold_starts_charging(self):
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value=self._data(2700)  # 270 W (threshold 260 W)
        )
        _run(cc.control_charging())
        self.assertTrue(cc.is_charging)

    def test_below_threshold_stops_charging(self):
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value=self._data(2500)  # 250 W
        )
        cc.is_charging = True
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)

    def test_exactly_at_threshold_stops_charging(self):
        # condition is strict ">" so equal → stop
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value=self._data(2600)  # exactly 260 W
        )
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)

    def test_multiple_inverters_are_summed(self):
        cc = _make_controller(threshold_watts=260)
        # Two inverters: 1500 + 1200 = 2700 tenths → 270 W > 260 W
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value=self._data(1500, 1200)
        )
        _run(cc.control_charging())
        self.assertTrue(cc.is_charging)

    def test_multiple_inverters_below_threshold(self):
        cc = _make_controller(threshold_watts=260)
        # 1200 + 1200 = 2400 tenths → 240 W < 260 W
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value=self._data(1200, 1200)
        )
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)

    def test_missing_active_power_key_treated_as_zero(self):
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value={"sgs": [{}]}
        )
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)


# ---------------------------------------------------------------------------
# control_charging — dtu_power fallback (no sgs entries)
# ---------------------------------------------------------------------------

class TestControlChargingDtuPowerFallback(unittest.TestCase):

    def test_dtu_power_above_threshold_starts_charging(self):
        cc = _make_controller(threshold_watts=260)
        # dtu_power is in W (not tenths), code multiplies by 10
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value={"dtu_power": 270, "sgs": []}
        )
        _run(cc.control_charging())
        self.assertTrue(cc.is_charging)

    def test_dtu_power_below_threshold_stops_charging(self):
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value={"dtu_power": 250, "sgs": []}
        )
        cc.is_charging = True
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)

    def test_sgs_present_takes_priority_over_dtu_power(self):
        cc = _make_controller(threshold_watts=260)
        # sgs sum = 2500 (250 W) < threshold; dtu_power = 300 W (would pass)
        _mock_dtu_instance.get_real_data_new = AsyncMock(
            return_value={"dtu_power": 300, "sgs": [{"active_power": 2500}]}
        )
        _run(cc.control_charging())
        # sgs wins → below threshold → not charging
        self.assertFalse(cc.is_charging)

    def test_empty_data_dict_does_not_raise(self):
        cc = _make_controller(threshold_watts=260)
        _mock_dtu_instance.get_real_data_new = AsyncMock(return_value={})
        _run(cc.control_charging())
        self.assertFalse(cc.is_charging)


if __name__ == "__main__":
    unittest.main()
