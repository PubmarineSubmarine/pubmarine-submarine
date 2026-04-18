from asyncio import sleep
import logging
logger = logging.getLogger(__name__)


try:
    import RPi.GPIO as GPIO
except RuntimeError:
    GPIO = None
    logger.warning("GPIO unavailable")


PICO_RESET_PIN = 18


def initialize_gpio():
    if not GPIO:
        return
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(PICO_RESET_PIN, GPIO.OUT)
    GPIO.output(PICO_RESET_PIN, GPIO.HIGH)
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
    GPIO.output(PICO_RESET_PIN, GPIO.LOW)
    await sleep(0.5)
    GPIO.output(PICO_RESET_PIN, GPIO.HIGH)
    logger.info("Pico reset via GPIO")
