import board
import pins

import analogio
import digitalio
import pwmio
import busio
import neopixel
import adafruit_mpu6050

from adafruit_motor import motor


# Main motors
_x1 = pwmio.PWMOut(pins.X1, frequency=440)
_x2 = pwmio.PWMOut(pins.X2, frequency=440)
_y1 = pwmio.PWMOut(pins.Y1, frequency=440)
_y2 = pwmio.PWMOut(pins.Y2, frequency=440)
_z1 = pwmio.PWMOut(pins.Z1, frequency=440)
_z2 = pwmio.PWMOut(pins.Z2, frequency=440)
#_w1 = pwmio.PWMOut(pins.W1, frequency=440)
#_w2 = pwmio.PWMOut(pins.W2, frequency=440)
motor_x = motor.DCMotor(_x1, _x2)
motor_y = motor.DCMotor(_y1, _y2)
motor_z = motor.DCMotor(_z1, _z2)
#motor_w = motor.DCMotor(_w1, _w2)
motor_x.decay_mode = motor.FAST_DECAY
motor_y.decay_mode = motor.FAST_DECAY
motor_z.decay_mode = motor.FAST_DECAY
#motor_w.decay_mode = motor.FAST_DECAY

# Jets
jet_fu = digitalio.DigitalInOut(pins.FU)
jet_fu.switch_to_output()
jet_fd = digitalio.DigitalInOut(pins.FD)
jet_fd.switch_to_output()
jet_fl = digitalio.DigitalInOut(pins.FL)
jet_fl.switch_to_output()
jet_fr = digitalio.DigitalInOut(pins.FR)
jet_fr.switch_to_output()
jet_ru = digitalio.DigitalInOut(pins.RU)
jet_ru.switch_to_output()
jet_rd = digitalio.DigitalInOut(pins.RD)
jet_rd.switch_to_output()
jet_rl = digitalio.DigitalInOut(pins.RL)
jet_rl.switch_to_output()
jet_rr = digitalio.DigitalInOut(pins.RR)
jet_rr.switch_to_output()

# Servos
# TODO

# WS2812B
pixels = neopixel.NeoPixel(pins.LED_DATA, 3)
led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()

# I2C/MPU6050
i2c = busio.I2C(pins.SCL, pins.SDA)
mpu = adafruit_mpu6050.MPU6050(i2c)

# Analog sensors
sensor_depth = analogio.AnalogIn(pins.SENS1)
sensor_battery = analogio.AnalogIn(pins.BAT_SENS)
