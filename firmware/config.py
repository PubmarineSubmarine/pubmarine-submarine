import microcontroller
import msgpack

from io import BytesIO


DEFAULT_CONFIG = {
    "watchdog": False,
    "watchdog_timeout": 2.5,
    "heartbeat": False,
    "heartbeat_timeout": 3,
    "stat_interval": 1,
    "sens_interval": 0,
    "disp_interval": 40,
    "autoreload": True,
    "reload_on_success": False,
    "reload_on_error": True,
    "jet_mapping": "ABCDEFGH",
    "battery_protection": True,
    "battery_warn_voltage": 10.5,
    "battery_critical_voltage": 9.9,
    "current_smoothing": 0.5,
}



def get_config():
    b = BytesIO(microcontroller.nvm[:])
    stored = msgpack.unpack(b)
    res = DEFAULT_CONFIG.copy()
    if isinstance(stored, dict) and stored.get("pubsub"):
        for k, v in stored.items():
            res[k] = v
    return res


def set_config(config):
    b = BytesIO()
    assert isinstance(config, dict)
    config["pubsub"] = 1
    msgpack.pack(config, b)
    val = b.getvalue()
    microcontroller.nvm[:len(val)] = val


def clear_config():
    b = BytesIO()
    msgpack.pack(-1, b)
    val = b.getvalue()
    microcontroller.nvm[:len(val)] = val
