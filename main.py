# main.py — AllPowers charge controller (MicroPython, ESP32-C6)
# BLE removed: polls Hoymiles DTU and controls relay directly.

import uasyncio as asyncio
import time
import machine
from charge_controller import ChargeController
from wifi import wifi_connect


# ----------------------------
# Config (edit as needed)
# ----------------------------
class Config:
    dtu_ip_address = "192.168.0.100"
    charge_threshold_watts = 260
    poll_interval_seconds = 5  # how often to check solar power
    start_time = 8  # 8 o clock
    end_time = 17  # 17 o clock


SSID = "YourSSID"
PASSWORD = "YourPw"


# ----------------------------
# Logging
# ----------------------------
def log_info(msg, *args):
    print("[INFO]", msg % args if args else msg)


def log_warn(msg, *args):
    print("[WARN]", msg % args if args else msg)


def log_error(msg, *args):
    print("[ERROR]", msg % args if args else msg)


def is_within_awake_time(cfg):
    now = time.localtime()
    current_minutes = now[3] * 60 + now[4]
    return cfg.start_time * 60 < current_minutes and cfg.end_time * 60 > current_minutes


def get_seconds_till_wake(cfg):
    now = time.localtime()
    current_minutes = now[3] * 60 + now[4]  # hours * 60 + minutes
    wake_minutes = cfg.start_time * 60  # convert start_time (hours) to minutes

    minutes_till_wake = (wake_minutes - current_minutes) % (24 * 60)
    return minutes_till_wake * 60


# ----------------------------
# Main loop
# ----------------------------
async def main():
    cfg = Config()
    try:
        wifi_connect(SSID, PASSWORD)
    except Exception as e:
        log_warn("WiFi connect failed: %s", e)

    controller = ChargeController(
        cfg.dtu_ip_address, cfg.charge_threshold_watts)

    while True:
        if is_within_awake_time(cfg):
            try:
                await controller.control_charging()
            except Exception as e:
                log_error("Control cycle error: %s", e)
            await asyncio.sleep(cfg.poll_interval_seconds)
        else:
            seconds_till_wake = get_seconds_till_wake(cfg)
            log_info("Not within specified turn on time frame. Sleep for %s seconds.", seconds_till_wake)

            machine.deepsleep(seconds_till_wake * 1000)
            
            if machine.reset_cause() == machine.DEEPSLEEP_RESET:
                print('woke from a deep sleep')


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.new_event_loop()
        except Exception:
            pass
