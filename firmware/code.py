import time
import sys
import select
import controls
import random
import usb_cdc
import microcontroller
import supervisor


MAX_BRIGHTNESS = 50
TICK_MS = 50
buffer = ""
last_tick_time = time.monotonic()
MOTOR_MIN = 0.2
MOTOR_MIN_START = 0.3
MOTOR_MAX_START = 0.5
MOTOR_MAX_CHANGE_TICK = 0.2
SV1_ADJUST = 0
SV2_ADJUST = 5
SV3_ADJUST = 0
SV4_ADJUST = 0

class Requests:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

requests = Requests()

def clamp(min, max, value):
    if value < min:
        return min
    elif value > max:
        return max
    else:
        return value

def soft_motor_control(motor, requested):
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
        if channel in ["X", "Y", "Z"]:
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
        if channel in ["SV1", "SV2", "SV3", "SV4"]:
            try:
                value = int(value)
            except Exception:
                do_error("Number format")
                continue
            if value < 0 or value > 180:
                do_error("Range")
                continue
        if channel == "X":
            # controls.motor_x.throttle = value
            requests.x = value
        elif channel == "Y":
            # controls.motor_y.throttle = value
            requests.y = value
        elif channel == "Z":
            # controls.motor_z.throttle = value
            requests.z = value
        # elif channel == "W":
        #     controls.motor_w.throttle = value
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
    controls.sv1.angle = clamp(0, 180, 90 + SV1_ADJUST)
    controls.sv2.angle = clamp(0, 180, 90 + SV2_ADJUST)

def do_error(params):
    print(f"ERR {params}")

cmd_stop("")

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

    print(f"# req x = {requests.x}, current x = {controls.motor_x.throttle}")
    print(f"# req y = {requests.y}, current y = {controls.motor_y.throttle}")
    print(f"# req z = {requests.z}, current z = {controls.motor_z.throttle}")
    soft_motor_control(controls.motor_x, requests.x)
    soft_motor_control(controls.motor_y, requests.y)
    soft_motor_control(controls.motor_z, requests.z)

    controls.led.value = not controls.led.value
    controls.pixels[0] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    controls.pixels[1] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    controls.pixels[2] = (random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS), random.randint(0, MAX_BRIGHTNESS))
    time_delta = time.monotonic() - last_tick_time
    # print("#", last_tick_time, time.monotonic(), time_delta)
    print(f"STAT X={controls.motor_x.throttle or 0.0} Y={controls.motor_y.throttle or 0.0} Z={controls.motor_z.throttle or 0.0} SV1={controls.sv1.angle or -1} " +
          f"SV2={controls.sv2.angle or -1} SV3={controls.sv3.angle or -1} SV4={controls.sv4.angle or -1} FU={int(controls.jet_fu.value)} " +
          f"FD={int(controls.jet_fd.value)} FL={int(controls.jet_fl.value)} FR={int(controls.jet_fr.value)} RU={int(controls.jet_ru.value)} " +
          f"RD={int(controls.jet_rd.value)} RL={int(controls.jet_rl.value)} RR={int(controls.jet_rr.value)} BAT={controls.sensor_battery.value / 65535.0 * 3.3 * 4} " +
          f"DEPTH={controls.sensor_depth.value / 65535.0} ACC={controls.mpu.acceleration[0]},{controls.mpu.acceleration[1]},{controls.mpu.acceleration[2]} " +
          f"GYRO={controls.mpu.gyro[0]},{controls.mpu.gyro[1]},{controls.mpu.gyro[2]}")
    time_to_sleep = TICK_MS/1000.0 - time_delta
    if time_to_sleep > 0:
        time.sleep(time_to_sleep)
    last_tick_time = time.monotonic()
