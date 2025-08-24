from asyncio import create_task, sleep
import serial
from serial_asyncio import open_serial_connection
import logging

from pydantic import ValidationError

from protocol import Command, StateCmd

logger = logging.getLogger(__name__)

class DebugSerialClient:
    def __init__(self, *args, **kwargs):
        self.callback = None

    async def connect(self):
        self.task = create_task(self.fake_state())

    def disconnect(self):
        pass
    async def write_cmd(self, cmd: Command):
        txt = cmd.serialize()
        logger.info(txt)
    async def fake_state(self):
        while True:
            try:
                await sleep(2)
                if self.callback:
                    await self.callback(StateCmd.default())
            except Exception:
                logger.exception("Error handling cmd")

class SerialClient:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.callback = None

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

    async def write_cmd(self, cmd: Command):
        await self.write_text(cmd.serialize() + "\n")

    async def write_text(self, text: str):
        try:
            logger.debug(f"TX: {text}")
            self.writer.write(text.encode("utf-8"))
            await self.writer.drain()
        except serial.SerialException:
            logger.exception("Error writing data")

    async def read_data(self) -> str | None:
        try:
            data = await self.reader.readline()
            text = data.decode("utf-8").strip()
            return text if text else None
        except Exception as e:
            logger.exception("Error reading data")
            if isinstance(e, serial.serialutil.SerialException):
                raise
            return None

    async def continuous_read(self):
        while True:
            try:
                data = await self.read_data()
            except serial.serialutil.SerialException:
                reader, writer = await open_serial_connection(
                    url=self.port, baudrate=self.baudrate
                )
                self.reader = reader
                self.writer = writer
                continue

            if data:
                if callback := self.callback:
                    # logger.debug(f"RX: {data}")
                    try:
                        cmd = Command.deserialize(data.strip())
                        if not isinstance(cmd, StateCmd):
                            logger.info(cmd)
                        await callback(cmd)
                    except ValidationError:
                        logger.debug(f"RX: {data}")
                else:
                    logger.debug(f"RX: {data}")

            await sleep(0.01)
