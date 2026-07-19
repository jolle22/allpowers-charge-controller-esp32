# main.py — AllPowers charge controller (MicroPython, ESP32-C6)
# BLE removed: polls Hoymiles DTU and controls relay directly.

import uasyncio as asyncio
import config
import time
import machine
import ntptime
import logging
from charge_controller import ChargeController
from wifi import wifi_connect

cfg = config.Config()

logging.basicConfig(
    level=logging.DEBUG,
    stream_level=logging.DEBUG,
    log_format="%(levelname)s:%(message)s",
    telegram_token = cfg.telegram_token,
    telegram_chat_id = cfg.telegram_chat_id,
    telegram_level = logging.INFO
)

async def control_charging(cfg, controller):
    while True:
        if is_within_awake_time(cfg):
            try:
                await controller.control_charging()
            except Exception as e:
                logging.error("Control cycle error: %s", e)
            await asyncio.sleep(cfg.poll_interval_seconds)
        else:
            controller.stop_charging(399999)

            seconds_till_wake = get_seconds_till_wake(cfg)
            logging.info(
                "Not within specified turn on time frame. Sleep for %s seconds.", seconds_till_wake)

            time.sleep(2) # wait a bit to make sure the switch has flipped!
            machine.deepsleep(seconds_till_wake * 1000)

            if machine.reset_cause() == machine.DEEPSLEEP_RESET:
                logging.info('woke from a deep sleep')


def set_time():
    try:
        ntptime.settime()
        logging.info("NTP sync done, UTC time: %s", time.localtime())
    except Exception as e:
        logging.warning("NTP setup failed: %s", e)


def local_time(utc_off_set_in_seconds):
    return time.localtime(time.time() + utc_off_set_in_seconds)


def is_within_awake_time(cfg):
    now = local_time(cfg.utc_off_set_in_seconds)
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
    logging.info("Monitoring DTU form %s till %s. Threshold is %s Watts.",
                 cfg.start_time, cfg.end_time, cfg.charge_threshold_watts)
    try:
        wifi_connect(cfg.ssid, cfg.password)
    except Exception as e:
        logging.warning("WiFi connection failed: %s", e)

    set_time()

    controller = ChargeController(
        cfg.dtu_ip_address, cfg.charge_threshold_watts)
    # await controller.test_charging()
    await control_charging(cfg, controller)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.new_event_loop()
        except Exception:
            pass

