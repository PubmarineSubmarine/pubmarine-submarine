from asyncio import create_task, sleep
import serial
from serial_asyncio import open_serial_connection
import logging

from pydantic import ValidationError

from protocol import Command, StateCmd, MotionCmd

logger = logging.getLogger(__name__)

class DebugSerialClient:
    def __init__(self, *args, **kwargs):
        self.callback = None
        self.gyro = [0.0, 0.0, 0.0]  # [roll, pitch, yaw]
        self.last_motion_cmd = None

    async def connect(self):
        self.task = create_task(self.fake_state())

    def disconnect(self):
        pass

    async def write_cmd(self, cmd: Command):
        txt = cmd.serialize()
        logger.info(txt)

        # Track MotionCmd to simulate gyro changes
        if isinstance(cmd, MotionCmd):
            self.last_motion_cmd = cmd

    async def fake_state(self):
        while True:
            try:
                await sleep(0.1)  # Update more frequently for smooth simulation
                if self.callback:
                    state = StateCmd.default()

                    # Simulate gyro changes based on last MotionCmd
                    if self.last_motion_cmd:
                        roll_delta = 0.0
                        pitch_delta = 0.0
                        yaw_delta = 0.0

                        if self.last_motion_cmd.sv1 is not None:
                            roll_delta = (self.last_motion_cmd.sv1 - 90) * 0.5  # Map 0-180 to degrees
                        if self.last_motion_cmd.sv2 is not None:
                            pitch_delta = (self.last_motion_cmd.sv2 - 90) * 0.5  # Map 0-180 to degrees

                        # Handle x and z axes - both control roll
                        if self.last_motion_cmd.x is not None:
                            roll_delta += self.last_motion_cmd.x * 10.0
                        if self.last_motion_cmd.z is not None:
                            roll_delta += self.last_motion_cmd.z * 10.0

                        left_thrust = 0
                        right_thrust = 0

                        if self.last_motion_cmd.fl: left_thrust += 1
                        if self.last_motion_cmd.rl: left_thrust += 1
                        if self.last_motion_cmd.fr: right_thrust += 1
                        if self.last_motion_cmd.rr: right_thrust += 1

                        yaw_delta += (right_thrust - left_thrust) * 1.5

                        self.gyro[0] += (roll_delta - self.gyro[0]) * 0.1  # roll
                        self.gyro[1] += (pitch_delta - self.gyro[1]) * 0.1  # pitch
                        self.gyro[2] += (yaw_delta - self.gyro[2]) * 0.1  # yaw

                        self.gyro[0] *= 0.95
                        self.gyro[1] *= 0.95
                        self.gyro[2] *= 0.95

                    state.gyro = tuple(round(v, 3) for v in self.gyro)
                    await self.callback(state)
            except Exception:
                logger.exception("Error handling cmd")

class SerialClient:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.callback = None
        self.connect_loop_task = None
        self.read_task = None
        self.writer = None
        self.reader = None

    async def _connect_loop(self):
        error_count = 0
        while True:
            try:
                reader, writer = await open_serial_connection(
                    url=self.port, baudrate=self.baudrate
                )
                logger.info(f"Successfully connected: {self.port}")
                self.reader = reader
                self.writer = writer

                if self.read_task:
                    self.read_task.cancel()
                self.read_task = create_task(self.continuous_read())
                return
            except serial.SerialException as e:
                await sleep(0.1)
                if error_count == 0:
                    logger.warning(f"Retrying - {e}")
                    error_count += 1

    async def connect(self):
        if self.connect_loop_task:
            self.connect_loop_task.cancel()
        self.connect_loop_task = create_task(self._connect_loop())


    def disconnect(self):
        if self.writer:
            self.writer.close()
        if task := self.read_task:
            task.cancel()
        logger.debug("Disconnected")

    async def write_cmd(self, cmd: Command):
        await self.write_text(cmd.serialize() + "\n")

    async def write_text(self, text: str):
        if not self.writer:
            return
        try:
            logger.debug(f"TX: {text}")
            self.writer.write(text.encode("utf-8"))
            await self.writer.drain()
        except serial.SerialException:
            #logger.exception("Error writing data")
            logger.warning(f"Failed to send serial command: {text}")

    async def read_line(self) -> str | None:
        data = await self.reader.readline()
        text = data.decode("utf-8").strip()
        return text if text else None


    async def continuous_read(self):
        while True:
            try:
                data = await self.read_line()
            except serial.SerialException:
                logger.warning(f"Disconnected {self.port}")
                await self.connect()
                return

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
