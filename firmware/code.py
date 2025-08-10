import time
import sys
import select
import controls
import random
import usb_cdc
import microcontroller
import supervisor


MAX_BRIGHTNESS = 50
TICK_MS = 500
buffer = ""
last_tick_time = time.monotonic()


def cmd_mot(params):
    commands = params.split(" ")
    for command in commands:
        channel, _, value = command.partition("=")
        if channel in ["X", "Y", "Z", "W"]:
            try:
                value = float(value)
            except Exception:
                do_error("Number format")
                continue
            if value < -1.0 or value > 1.0:
                do_error("Range")
                continue
        if channel in ["FU", "FD", "FL", "FR", "RU", "RD", "RL", "RR"]:
            try:
                value = int(value)
            except Exception:
                do_error("Number format")
                continue
            if value not in [0, 1]:
                do_error("Range")
                continue
        # TODO servo range
        if channel == "X":
            controls.motor_x.throttle = value
        elif channel == "Y":
            controls.motor_y.throttle = value
        elif channel == "Z":
            controls.motor_z.throttle = value
        elif channel == "W":
            controls.motor_w.throttle = value
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
    controls.motor_x.throttle = 0
    controls.motor_y.throttle = 0
    controls.motor_z.throttle = 0
    # controls.motor_w.throttle = 0
    controls.jet_fu.value = False
    controls.jet_fd.value = False
    controls.jet_fl.value = False
    controls.jet_fr.value = False
    controls.jet_ru.value = False
    controls.jet_rd.value = False
    controls.jet_rl.value = False
    controls.jet_rr.value = False
    # TODO servos

def do_error(params):
    print(f"ERR {params}")

# Main loop
while True:
    while select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        buffer += sys.stdin.read(1)
        if buffer[-1] == '\x08':
            buffer = buffer[0:-2]
    # print(repr(buffer))
    lines = []
    while "\n" in buffer:
        line, _, buffer = buffer.partition("\n")
        lines.append(line)

    # Main dispatch
    for line in lines:
        cmd, _, tail = line.partition(" ")
        tail = tail.strip()
        if cmd == "MOT":
            cmd_mot(tail)
        elif cmd == "RESET":
            cmd_reset(tail)
        elif cmd == "BOOT":
            cmd_boot(tail)
        elif cmd == "STOP":
            cmd_stop(tail)
        else:
            do_error("Unknown command")

    #if usb_cdc.console.in_waiting:
    #    print(usb_cdc.console.read(usb_cdc.console.in_waiting))
    print(controls.mpu.acceleration, controls.mpu.gyro)
    controls.led.value = not controls.led.value
    controls.pixels[0] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    controls.pixels[1] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    controls.pixels[2] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    time_delta = time.monotonic() - last_tick_time
    print(last_tick_time, time.monotonic(), time_delta)
    time.sleep(TICK_MS/1000.0 - time_delta)
    last_tick_time = time.monotonic()
