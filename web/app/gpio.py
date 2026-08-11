import logging
from asyncio import sleep

logger = logging.getLogger(__name__)


try:
    import RPi.GPIO as GPIO
except (RuntimeError, ModuleNotFoundError):
    GPIO = None
    logger.warning("GPIO unavailable")


PICO_RESET_PIN = 18


def initialize_gpio():
    if not GPIO:
        return
    GPIO.setmode(GPIO.BCM)

    # never output high, pressing reset button on board would short to ground
    # instead we use high-Z input for run and output low for reset
    GPIO.setup(PICO_RESET_PIN, GPIO.IN, GPIO.PUD_OFF)
    logger.debug(f"GPIO initialized. Using pin {PICO_RESET_PIN} for reset")


def cleanup_gpio():
    if not GPIO:
        return
    GPIO.cleanup()


async def reset_pico():
    if not GPIO:
        logger.info("Ignoring reset command - GPIO unavailable")
        return
    logger.debug("Reseting pico...")
    GPIO.setup(PICO_RESET_PIN, GPIO.OUT)
    GPIO.output(PICO_RESET_PIN, GPIO.LOW)
    await sleep(0.5)
    GPIO.setup(PICO_RESET_PIN, GPIO.IN, GPIO.PUD_OFF)
    logger.info("Pico reset via GPIO")
