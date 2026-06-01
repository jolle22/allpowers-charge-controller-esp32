# config.py — local configuration, not committed to version control

class Config:
    dtu_ip_address = "192.168.0.100"
    charge_threshold_watts = 260
    poll_interval_seconds = 5  # how often to check solar power
    start_time = 8  # 8 o clock
    end_time = 17  # 17 o clock
    ssid = "YourSSID"
    password = "YourPw"
    utc_off_set_in_seconds=2 * 3600  # UTC+2 (CEST), change to 1 * 3600 in winter (CET)
