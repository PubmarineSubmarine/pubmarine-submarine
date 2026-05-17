import time
import sys
import select
import controls
# import mock_controls as controls
import display
import random
import usb_cdc
import microcontroller
import supervisor
import json
import watchdog

from config import get_config, set_config, clear_config


config = get_config()

MAX_BRIGHTNESS = 10
TICK_MS = 50
buffer = ""
last_tick_time = time.monotonic()
last_heartbeat_time = time.monotonic()
last_heartbeat_lost_time = time.monotonic()
tick_number = 0
MOTOR_MIN = 0.2
MOTOR_MIN_START = 0.3
MOTOR_MAX_START = 0.5
MOTOR_MAX_CHANGE_TICK = 0.2
SV1_ADJUST = 0
SV2_ADJUST = 5
SV3_ADJUST = 0
SV4_ADJUST = 0
MOTOR_A_SCALE = 1.0
MOTOR_B_SCALE = -1.0

class Requests:
    a: float = 0.0
    b: float = 0.0

requests = Requests()

def clamp(min, max, value):
    if value < min:
        return min
    elif value > max:
        return max
    else:
        return value

def soft_motor_control(motor, requested):
    if motor == controls.motor_a:
        requested *= MOTOR_A_SCALE
    elif motor == controls.motor_b:
        requested *= MOTOR_B_SCALE
    if requested != motor.throttle:
        if abs(requested) < MOTOR_MIN:
            motor.throttle = 0
        elif motor.throttle == 0 and abs(requested) < MOTOR_MIN_START:
            pass
        elif motor.throttle == 0 and abs(requested) > MOTOR_MAX_START:
            sign = requested / abs(requested)
            motor.throttle = sign * MOTOR_MAX_START
        else:
            delta = requested - motor.throttle
            if abs(delta) > MOTOR_MAX_CHANGE_TICK:
                sign = delta / abs(delta)
                motor.throttle += sign * MOTOR_MAX_CHANGE_TICK
            else:
                motor.throttle = requested

def soft_servo_control(servo, requested):
    requested = clamp(10, 170, requested)
    if servo == controls.sv1:
        controls.sv1.angle = clamp(0, 180, requested + SV1_ADJUST)
    elif servo == controls.sv2:
        controls.sv2.angle = clamp(0, 180, requested + SV2_ADJUST)

def cmd_mot(params):
    commands = params.split(" ")
    for command in commands:
        channel, _, value = command.partition("=")
        if channel in ["A", "B"]:
            try:
                value = float(value)
            except Exception:
                do_error("Number format")
                continue
            if value < -1.0 or value > 1.0:
                do_error("Range")
                continue
        if channel in ["FU", "FD", "FL", "FR", "RU", "RD", "RL", "RR", "LIGHTS"]:
            try:
                value = int(value)
            except Exception:
                do_error("Number format")
                continue
            if value not in [0, 1]:
                do_error("Range")
                continue
        # TODO servo range
        if channel in ["SV1", "SV2", "SV3", "SV4"]:
            try:
                value = int(value)
            except Exception:
                do_error("Number format")
                continue
            if value < 0 or value > 180:
                do_error("Range")
                continue
        if channel == "A":
            # controls.motor_a.throttle = value
            requests.a = value
        elif channel == "B":
            # controls.motor_b.throttle = value
            requests.b = value
        elif channel == "FU":
            controls.jet_fu.value = bool(value)
        elif channel == "FD":
            controls.jet_fd.value = bool(value)
        elif channel == "FL":
            controls.jet_fl.value = bool(value)
        elif channel == "FR":
            controls.jet_fr.value = bool(value)
        elif channel == "RU":
            controls.jet_ru.value = bool(value)
        elif channel == "RD":
            controls.jet_rd.value = bool(value)
        elif channel == "RL":
            controls.jet_rl.value = bool(value)
        elif channel == "RR":
            controls.jet_rr.value = bool(value)
        elif channel == "SV1":
            soft_servo_control(controls.sv1, value)
        elif channel == "SV2":
            soft_servo_control(controls.sv2, value)
        elif channel == "SV3":
            controls.sv3.angle = value
        elif channel == "SV4":
            controls.sv4.angle = value
        elif channel == "LIGHTS":
            controls.lights.value = bool(value)

def cmd_reset(params):
    if params == "SOFT":
        supervisor.reload()
    elif params == "SAFE":
        microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
        microcontroller.reset()
    else:
        microcontroller.on_next_reset(microcontroller.RunMode.NORMAL)
        microcontroller.reset()

def cmd_boot(params):
    microcontroller.on_next_reset(microcontroller.RunMode.UF2)
    microcontroller.reset()

def cmd_stop(params):
    controls.motor_a.throttle = 0
    controls.motor_b.throttle = 0
    requests.a = 0
    requests.b = 0
    controls.jet_fu.value = False
    controls.jet_fd.value = False
    controls.jet_fl.value = False
    controls.jet_fr.value = False
    controls.jet_ru.value = False
    controls.jet_rd.value = False
    controls.jet_rl.value = False
    controls.jet_rr.value = False
    controls.sv1.angle = clamp(0, 180, 90 + SV1_ADJUST)
    controls.sv2.angle = clamp(0, 180, 90 + SV2_ADJUST)
    print("STOP")


def cmd_test(params):
    INTERVAL = 1.0
    cmd_stop("")
    controls.motor_a.throttle = 1
    controls.sv1.angle = 45
    controls.lights.value = True
    time.sleep(INTERVAL)
    controls.motor_a.throttle = 0
    controls.sv1.angle = 90
    controls.motor_b.throttle = 1
    controls.sv2.angle = 45
    controls.lights.value = False
    time.sleep(INTERVAL)
    controls.sv2.angle = 90
    controls.motor_b.throttle = 0
    controls.motor_a.throttle = -1
    time.sleep(INTERVAL)
    controls.motor_a.throttle = 0
    controls.motor_b.throttle = -1
    time.sleep(INTERVAL)
    # controls.jet_fu.value = True
    # time.sleep(INTERVAL)
    # controls.jet_fu.value = False
    # controls.jet_fd.value = True
    # time.sleep(INTERVAL)
    # controls.jet_fd.value = False
    # controls.jet_fl.value = True
    # time.sleep(INTERVAL)
    # controls.jet_fl.value = False
    # controls.jet_fr.value = True
    # time.sleep(INTERVAL)
    # controls.jet_fr.value = False
    # controls.jet_ru.value = True
    # time.sleep(INTERVAL)
    # controls.jet_ru.value = False
    # controls.jet_rd.value = True
    # time.sleep(INTERVAL)
    # controls.jet_rd.value = False
    # controls.jet_rl.value = True
    # time.sleep(INTERVAL)
    # controls.jet_rl.value = False
    # controls.jet_rr.value = True
    # time.sleep(INTERVAL)
    cmd_stop("")


def cmd_error(params):
    raise ValueError(params)

def cmd_get_config(params):
    print(f"CONFIG {json.dumps(config)}")

def cmd_set_config(params):
    new_config = json.loads(params)
    for k, v in new_config.items():
        config[k] = v
    set_config(config)
    print(json.dumps(config))

def cmd_clear_config(params):
    clear_config()
    config = get_config()
    print(json.dumps(config))

def do_error(params):
    print(f"ERR {params}")

cmd_stop("")

supervisor.runtime.autoreload = config.get("autoreload", True)
supervisor.set_next_code_file(None, reload_on_success=config.get("reload_on_success", False), reload_on_error=config.get("reload_on_error", True), sticky_on_success=True, sticky_on_error=True)

if config.get("watchdog"):
    print("# enabling watchdog")
    microcontroller.watchdog.timeout = 2.5
    microcontroller.watchdog.mode = watchdog.WatchDogMode.RESET
else:
    print("# not enabling watchdog")


try:
    controls.sleep_m.value = True
    controls.sleep_j.value = True

    # Main loop
    while True:
        microcontroller.watchdog.feed()
        if not supervisor.runtime.serial_connected:
            print("# serial disconnected")
            cmd_stop("")
        while select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            buffer += sys.stdin.read(1)
            if buffer[-1] in ('\x08', '\x7f'):
                buffer = buffer[0:-2]
        # print(repr(buffer))
        lines = []
        while "\n" in buffer:
            line, _, buffer = buffer.partition("\n")
            line = line.strip()
            if line:
                lines.append(line)

        # Main dispatch
        for line in lines:
            last_heartbeat_time = time.monotonic()
            cmd, _, tail = line.partition(" ")
            cmd = cmd.upper()
            tail = tail.strip()
            if cmd == "MOT":
                cmd_mot(tail)
            elif cmd == "RESET":
                cmd_reset(tail)
            elif cmd == "BOOT":
                cmd_boot(tail)
            elif cmd == "STOP":
                cmd_stop(tail)
            elif cmd == "TEST":
                cmd_test(tail)
            elif cmd == "ERROR":
                cmd_error(tail)
            elif cmd == "GET_CONFIG":
                cmd_get_config(tail)
            elif cmd == "SET_CONFIG":
                cmd_set_config(tail)
            elif cmd == "CLEAR_CONFIG":
                cmd_clear_config(tail)
            elif cmd == "PING":
                print("PONG")
            elif cmd == "REPL":
                print("# disabling watchdog")
                microcontroller.watchdog.mode = None
                # this breaks to REPL even when reload_on_success is True
                # controls.i2c.deinit()
                sys.exit(0)
            else:
                do_error("Unknown command")

        # print(f"# req a = {requests.a}, current a = {controls.motor_a.throttle}")
        # print(f"# req b = {requests.b}, current b = {controls.motor_b.throttle}")
        soft_motor_control(controls.motor_a, requests.a)
        soft_motor_control(controls.motor_b, requests.b)

        controls.led.value = not controls.led.value
        for i in range(len(controls.pixels)):
            controls.pixels[i] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
        time_delta = time.monotonic() - last_tick_time
        acc = (-1.0, -1.0, -1.0)
        gyro = (-1.0, -1.0, -1.0)
        # print("#", last_tick_time, time.monotonic(), time_delta)
        try:
            if hasattr(controls, "mpu"):
                acc = controls.mpu.acceleration
                gyro = controls.mpu.gyro
            else:
                acc = (-1.0, -1.0, -1.0)
                gyro = (-1.0, -1.0, -1.0)
        except Exception as e:
            import traceback
            traceback.print_exception(e)
            acc = (-1.0, -1.0, -1.0)
            gyro = (-1.0, -1.0, -1.0)
        if config.get("stat_interval", 1) > 0 and tick_number % config["stat_interval"] == 0:
            print(f"STAT A={controls.motor_a.throttle or 0.0} B={controls.motor_b.throttle or 0.0} SV1={controls.sv1.angle or -1} " +
                  f"SV2={controls.sv2.angle or -1} SV3={controls.sv3.angle or -1} SV4={controls.sv4.angle or -1} FU={int(controls.jet_fu.value)} " +
                  f"FD={int(controls.jet_fd.value)} FL={int(controls.jet_fl.value)} FR={int(controls.jet_fr.value)} RU={int(controls.jet_ru.value)} " +
                  f"RD={int(controls.jet_rd.value)} RL={int(controls.jet_rl.value)} RR={int(controls.jet_rr.value)} " +
                  f"LIGHTS={int(controls.lights.value)} BAT={controls.sensor_battery.voltage * 4} " +
                  f"DEPTH={controls.sensor_depth.value / 65535.0} ACC={acc[0]},{acc[1]},{acc[2]} " +
                  f"GYRO={gyro[0]},{gyro[1]},{gyro[2]} " +
                  f"TEMP={controls.aht.temperature} HUM={controls.aht.relative_humidity} " +
                  f"MCU={microcontroller.cpu.temperature}")
        if config.get("heartbeat"):
            if time.monotonic() - last_heartbeat_time >= 10 and last_heartbeat_lost_time < last_heartbeat_time:
                print("# heartbeat lost, stopping motors")
                last_heartbeat_lost_time = time.monotonic()
                cmd_stop("")
        time_to_sleep = TICK_MS/1000.0 - time_delta
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)
        last_tick_time = time.monotonic()
        tick_number += 1
except KeyboardInterrupt:
    print("# got interrupt")
    print("# disabling watchdog")
    microcontroller.watchdog.mode = None
    # controls.i2c.deinit()
