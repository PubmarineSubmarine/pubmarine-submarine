import board
import pins

import analogio
import digitalio
import pwmio
import busio
import neopixel
import adafruit_mpu6050_patched as adafruit_mpu6050
import adafruit_ads1x15.ads1015
import adafruit_ads1x15.analog_in
import adafruit_ahtx0
import displayio
import i2cdisplaybus
import adafruit_displayio_ssd1306

from adafruit_motor import motor, servo


# Main motors
_a1 = pwmio.PWMOut(pins.A1, frequency=440)
_a2 = pwmio.PWMOut(pins.A2, frequency=440)
_b1 = pwmio.PWMOut(pins.B1, frequency=440)
_b2 = pwmio.PWMOut(pins.B2, frequency=440)
motor_a = motor.DCMotor(_a1, _a2)
motor_b = motor.DCMotor(_b1, _b2)
motor_a.decay_mode = motor.FAST_DECAY
motor_b.decay_mode = motor.FAST_DECAY
sleep_m = digitalio.DigitalInOut(pins.SLEEP_M)
sleep_m.switch_to_output()
fault_m = digitalio.DigitalInOut(pins.FAULT_M)
fault_m.switch_to_input()

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
sleep_j = digitalio.DigitalInOut(pins.SLEEP_J)
sleep_j.switch_to_output()
fault_j = digitalio.DigitalInOut(pins.FAULT_J)
fault_j.switch_to_input()

# Servos
_sv1 = pwmio.PWMOut(pins.SV1, frequency=50, duty_cycle=0)
sv1 = servo.Servo(_sv1, min_pulse=500, max_pulse=2500, actuation_range=180)
_sv2 = pwmio.PWMOut(pins.SV2, frequency=50, duty_cycle=0)
sv2 = servo.Servo(_sv2, min_pulse=500, max_pulse=2500, actuation_range=180)
_sv3 = pwmio.PWMOut(pins.SV3, frequency=50, duty_cycle=0)
sv3 = servo.Servo(_sv3, min_pulse=500, max_pulse=2500, actuation_range=180)
_sv4 = pwmio.PWMOut(pins.SV4, frequency=50, duty_cycle=0)
sv4 = servo.Servo(_sv4, min_pulse=500, max_pulse=2500, actuation_range=180)

lights = digitalio.DigitalInOut(pins.LIGHTS)
lights.switch_to_output()

# WS2812B
pixels = neopixel.NeoPixel(pins.LED_DATA, 3)
led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()

# I2C/MPU6050
displayio.release_displays()
i2c = busio.I2C(pins.SCL, pins.SDA, frequency=400000)
mpu = adafruit_mpu6050.MPU6050(i2c)
try:
    ads = adafruit_ads1x15.ads1015.ADS1015(i2c, gain=1, data_rate=1600, mode=adafruit_ads1x15.ads1x15.Mode.SINGLE)
    aht = adafruit_ahtx0.AHTx0(i2c)
    display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3c)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=32, auto_refresh=False)

    # Analog sensors
    sensor_depth = adafruit_ads1x15.analog_in.AnalogIn(ads, adafruit_ads1x15.ads1015.P3)
    sensor_battery = adafruit_ads1x15.analog_in.AnalogIn(ads, adafruit_ads1x15.ads1015.P2)
    sensor_ipropi_a = adafruit_ads1x15.analog_in.AnalogIn(ads, adafruit_ads1x15.ads1015.P1)
    sensor_ipropi_b = adafruit_ads1x15.analog_in.AnalogIn(ads, adafruit_ads1x15.ads1015.P0)
except ValueError as e:
    import traceback
    traceback.print_exception(e)
    print("Falling back to mocks")
    from mock_controls import *
