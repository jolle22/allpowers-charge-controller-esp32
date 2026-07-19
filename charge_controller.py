"""
charge_controller.py — Hoymiles DTU integration for AllPowers charge controller.

Replaces the old SimpleDTU / heuristic protobuf parser with the proper
hoymiles-wifi DTU client (dtu.py from hoymiles-wifi/micropython).

The DTU class from hoymiles-wifi/micropython must be present on the device
alongside this file:
    ucrc16.py, ucrypt.py, upb.py, dtu.py  (from hoymiles-wifi/micropython)

active_power is returned by get_real_data_new() in tenths of watts (÷10 = W).
The charge threshold comparison is done in the same unit for consistency with
the existing logic in BatteryMonitor.
"""

import uasyncio as asyncio
from machine import Pin
import logging # https://github.com/erikdelange/MicroPython-Logging/blob/main/logging.py

# Import the proper DTU client from hoymiles-wifi/micropython
from dtu import DTU as HoymilesDTU

RELAY_PIN_NUMBER = 5  # GPIO5

logging.basicConfig(
    level=logging.DEBUG,
    stream_level=logging.DEBUG        # Console output level
)

class ChargeController:
    """
    Controls an external relay (GPIO16) based on solar power output from the
    Hoymiles DTU.  Replaces the old SimpleDTU-based implementation.
    """

    def __init__(self, dtu_ip_address: str, charge_threshold_watts: int,
                 is_encrypted: bool = False, enc_rand: bytes = b""):
        
        logging.debug("dtu address: " + dtu_ip_address)
        self._dtu = HoymilesDTU(dtu_ip_address,
                                is_encrypted=is_encrypted,
                                enc_rand=enc_rand)
        # Threshold stored in tenths of watts to match what the DTU returns
        self._threshold_x10 = charge_threshold_watts * 10
        self.relay_pin = Pin(RELAY_PIN_NUMBER, Pin.OUT)
        self.state = ""
        self.stop_charging(199999)

    # ------------------------------------------------------------------
    # Relay helpers
    # ------------------------------------------------------------------

    def start_charging(self, total_power):
        self.is_charging = True
        self.relay_pin.value(0)
        logging.debug("[ChargeController] External charging started ✅.")
        
        if(self.state != "started"):
            self.state = "started"
            logging.telegram("Charging ✅. ⚡ "+str(total_power / 10))            
            

    def stop_charging(self, total_power):
        self.is_charging = False
        self.relay_pin.value(1)
        logging.debug("[ChargeController] External charging stopped 🚫.")
        
        if(self.state != "stopped" or total_power > 99999):
            self.state = "stopped"
            logging.telegram("Charging 🚫. ⚡"+str(total_power / 10))

    # ------------------------------------------------------------------
    # Main control cycle
    # ------------------------------------------------------------------

    async def control_charging(self):
        """
        Query the DTU for real-time solar power and start/stop the relay.
        Call this once per monitoring loop iteration.
        """
        data = await self._dtu.get_real_data_new()

        if data is None:
            logging.info("[ChargeController] No response from DTU — skipping cycle.")
            return

        # dtu.get_real_data_new() returns active_power in tenths of watts
        # for each SGS (single-phase inverter) entry.
        # Sum all inverters so multi-MPPT setups work correctly.
        total_power_x10 = 0
        for inv in data.get("sgs", []):
            total_power_x10 += inv.get("active_power", 0)

        # Also include dtu_power as a fallback when no sgs entries are present
        if not data.get("sgs"):
            # dtu_power is already in W (not tenths) per the hoymiles-wifi parser
            total_power_x10 = data.get("dtu_power", 0) * 10

        logging.debug("[ChargeController] Solar power: {:.1f} W  threshold: {:.1f} W".format(
            total_power_x10 / 10, self._threshold_x10 / 10))

        if total_power_x10 > self._threshold_x10:
            self.start_charging(total_power_x10)
        else:
            self.stop_charging(total_power_x10)

    async def test_charging(self):
        """
        Starts and stops charing every 3 seconds
        """
        is_off = True
        
        while True:
            if is_off:
                self.start_charging()
            else:
                self.stop_charging()
            is_off = not is_off
            await asyncio.sleep(3)
