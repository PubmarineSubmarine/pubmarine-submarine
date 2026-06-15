import board
import digitalio
import neopixel
import random


class MockMotor:
    throttle = 0.0


class MockServo:
    angle = 0


class MockDigitalIO:
    value = False


class MockAnalogIn:
    @property
    def value(self):
        return 0.0


class MockBattery:
    _max_voltage = 12.6
    _min_voltage = 9.8
    _voltage = _max_voltage

    @property
    def value(self):
        if self._voltage > self._min_voltage:
            self._voltage -= 0.001
        voltage = self._voltage + random.uniform(-0.1, 0.1)
        return voltage / 4 / 3.3 * 65535


motor_x = MockMotor()
motor_y = MockMotor()
motor_z = MockMotor()
jet_fu = MockDigitalIO()
jet_fd = MockDigitalIO()
jet_fl = MockDigitalIO()
jet_fr = MockDigitalIO()
jet_ru = MockDigitalIO()
jet_rd = MockDigitalIO()
jet_rl = MockDigitalIO()
jet_rr = MockDigitalIO()
sv1 = MockServo()
sv2 = MockServo()
sv3 = MockServo()
sv4 = MockServo()
# pixels = neopixel.NeoPixel(board.NEOPIXEL, 1)
led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()
sensor_depth = MockAnalogIn()
sensor_battery = MockBattery()
