from asyncio import create_task, sleep
import serial
from serial_asyncio import open_serial_connection
import logging

logger = logging.getLogger(__name__)


class SerialClient:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate

    async def connect(self):
        reader, writer = await open_serial_connection(
            url=self.port, baudrate=self.baudrate
        )
        self.reader = reader
        self.writer = writer
        self.read_task = create_task(self.continuous_read())

    def disconnect(self):
        if self.writer:
            self.writer.close()
        if task := self.read_task:
            task.cancel()
        logger.debug("Disconnected")

    async def write_text(self, text: str):
        try:
            await self.writer.write(text.encode("utf-8"))
            await self.writer.drain()
            logger.debug(f"TX: {text}")
        except serial.SerialException:
            logger.exception("Error writing data")

    async def read_data(self) -> str | None:
        try:
            data = await self.reader.readline()
            text = data.decode("utf-8").strip()
            return text if text else None
        except Exception:
            logger.exception("Error reading data")
            return None

    async def continuous_read(self):
        while True:
            data = self.read_data()
            if data:
                logger.debug(f"RX: {data}")
            await sleep(0.01)
