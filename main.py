# main.py — AllPowers charge controller (MicroPython, ESP32-C6)
# BLE removed: polls Hoymiles DTU and controls relay directly.

import uasyncio as asyncio
import config
import time
import machine
import ntptime
import logging # https://github.com/Me-Phew/micropython-logging/blob/main/logging.py
from charge_controller import ChargeController
from wifi import wifi_connect

logging.basicConfig(
        level=logging.DEBUG,
        stream_level=logging.DEBUG,        # Console output level
        filename="log.txt",
        file_level=logging.DEBUG          # File output level
        )

UTC_OFFSET_SECONDS = 2 * 3600


def set_time(utc_off_set_in_seconds):
    try:
        ntptime.settime()
        global UTC_OFFSET_SECONDS
        UTC_OFFSET_SECONDS = utc_off_set_in_seconds
        logging.info("NTP sync done, UTC time: %s", time.localtime())
    except Exception as e:
        logging.warning("NTP setup failed: %s", e)


def local_time():
    return time.localtime(time.time() + UTC_OFFSET_SECONDS)


def is_within_awake_time(cfg):
    now = local_time()
    current_minutes = now[3] * 60 + now[4]
    return cfg.start_time * 60 < current_minutes and cfg.end_time * 60 > current_minutes


def get_seconds_till_wake(cfg):
    now = local_time()
    current_minutes = now[3] * 60 + now[4]  # hours * 60 + minutes
    wake_minutes = cfg.start_time * 60  # convert start_time (hours) to minutes

    minutes_till_wake = (wake_minutes - current_minutes) % (24 * 60)
    return minutes_till_wake * 60


# ----------------------------
# Main loop
# ----------------------------
async def main():
    cfg = config.Config()
    logging.info("Monitoring DTU form %s till %s", cfg.start_time, cfg.end_time)
    try:
        wifi_connect(cfg.ssid, cfg.password)
    except Exception as e:
        logging.warning("WiFi connection failed: %s", e)

    set_time(cfg.utc_off_set_in_seconds)

    controller = ChargeController(
        cfg.dtu_ip_address, cfg.charge_threshold_watts)

    while True:
        if is_within_awake_time(cfg):
            try:
                await controller.control_charging()
            except Exception as e:
                logging.error("Control cycle error: %s", e)
            await asyncio.sleep(cfg.poll_interval_seconds)
        else:
            controller.stop_charging()

            seconds_till_wake = get_seconds_till_wake(cfg)
            logging.info("Not within specified turn on time frame. Sleep for %s seconds.", seconds_till_wake)

            machine.deepsleep(seconds_till_wake * 1000)

            if machine.reset_cause() == machine.DEEPSLEEP_RESET:
                logging.info('woke from a deep sleep')


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.new_event_loop()
        except Exception:
            pass
