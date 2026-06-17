import logging
import random
import traceback
from asyncio import create_task, sleep
from typing import Optional

import serial
from protocol import Command, ConsoleLog, MotionCmd, StateCmd
from pydantic import ValidationError
from serial.tools.list_ports import comports
from serial_asyncio import open_serial_connection

logger = logging.getLogger(__name__)


async def default_callback(msg: Command):
    pass


class DebugSerialClient:
    def __init__(self, *args, **kwargs):
        self.callback = default_callback
        self.gyro = [0.0, 0.0, 0.0]  # [roll, pitch, yaw]
        self.last_motion_cmd = None

    async def connect(self):
        self.task = create_task(self.fake_state())

    def disconnect(self):
        pass

    async def write_text(self, text: str):
        logger.info(f"debug serial tx: {repr(text)}")

    async def write_cmd(self, cmd: Command):
        txt = cmd.serialize()
        logger.info(txt)

        # Track MotionCmd to simulate gyro changes
        if isinstance(cmd, MotionCmd):
            self.last_motion_cmd = cmd

            # Immediately send state update for responsive feedback
            if self.callback:
                state = StateCmd.default()

                # Calculate gyro based on the new command
                roll_delta = 0.0
                pitch_delta = 0.0
                yaw_delta = 0.0

                if cmd.sv1 is not None:
                    roll_delta = (cmd.sv1 - 90) * 0.5
                if cmd.sv2 is not None:
                    pitch_delta = (cmd.sv2 - 90) * 0.5

                if cmd.a is not None:
                    roll_delta += cmd.a * 10.0
                if cmd.b is not None:
                    roll_delta += cmd.b * 10.0

                left_thrust = 0
                right_thrust = 0

                if cmd.fl:
                    left_thrust += 1
                if cmd.rl:
                    left_thrust += 1
                if cmd.fr:
                    right_thrust += 1
                if cmd.rr:
                    right_thrust += 1

                yaw_delta = (right_thrust - left_thrust) * 15.0

                self.gyro[0] += (roll_delta - self.gyro[0]) * 0.5
                self.gyro[1] += (pitch_delta - self.gyro[1]) * 0.1
                self.gyro[2] += yaw_delta * 0.3

                self.gyro[0] *= 0.95
                self.gyro[1] *= 0.95
                self.gyro[2] *= 0.98

                state.gyro = tuple(round(v, 3) for v in self.gyro)
                await self.callback(state)

    async def fake_state(self):
        while True:
            try:
                await sleep(0.1)  # Update more frequently for smooth simulation
                if self.callback:
                    if random.randint(0, 100) == 0:
                        await self.callback(ConsoleLog(line="This is a test message from the debug PICO serial client"))
                    elif random.randint(0, 1000) == 0:
                        await self.callback(MotionCmd(a=1.0, b=-2.7, fl=29))

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
                        if self.last_motion_cmd.a is not None:
                            roll_delta += self.last_motion_cmd.a * 10.0
                        if self.last_motion_cmd.b is not None:
                            roll_delta += self.last_motion_cmd.b * 10.0

                        left_thrust = 0
                        right_thrust = 0

                        if self.last_motion_cmd.fl:
                            left_thrust += 1
                        if self.last_motion_cmd.rl:
                            left_thrust += 1
                        if self.last_motion_cmd.fr:
                            right_thrust += 1
                        if self.last_motion_cmd.rr:
                            right_thrust += 1

                        yaw_delta = (right_thrust - left_thrust) * 15.0

                        self.gyro[0] += (roll_delta - self.gyro[0]) * 0.5  # roll
                        self.gyro[1] += (pitch_delta - self.gyro[1]) * 0.1  # pitch
                        self.gyro[2] += yaw_delta * 0.3  # yaw accumulates

                        self.gyro[0] *= 0.95
                        self.gyro[1] *= 0.95
                        # Don't decay yaw as much so rotation is visible
                        self.gyro[2] *= 0.98

                    state.gyro = tuple(round(v, 3) for v in self.gyro)
                    await self.callback(state)
            except Exception:
                logger.exception("Error handling cmd")


class SerialClient:
    def __init__(self, port: Optional[str] = None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.callback = default_callback
        self.connect_loop_task = None
        self.read_task = None
        self.writer = None
        self.reader = None

    def _discover_ports(self) -> list[str]:
        ports = [device.device for device in comports() if "ttyACM" in device.device]
        if ports:
            logger.debug(f"Discovered serial ports: {ports}")
        return ports

    async def _connect_loop(self):
        error_count = 0
        while True:
            ports_to_try = [self.port] if self.port else self._discover_ports()
            for port in ports_to_try:
                try:
                    reader, writer = await open_serial_connection(url=port, baudrate=self.baudrate)
                    logger.info(f"Successfully connected: {port}")
                    self.reader = reader
                    self.writer = writer

                    if self.read_task:
                        self.read_task.cancel()
                    self.read_task = create_task(self.continuous_read())
                    return
                except serial.SerialException as e:
                    logger.debug(f"Failed to connect to {port}: {e}")
            await sleep(0.1)
            if error_count % 50 == 0:
                logger.warning(f"Retrying - no serial ports available or all connection attempts failed")
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
        if self.connect_loop_task:
            self.connect_loop_task.cancel()
        self.connect_loop_task = create_task(self._connect_loop())

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
            # logger.exception("Error writing data")
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
                    logger.debug(f"RX: {data}")
                    try:
                        cmd = Command.deserialize(data.strip())
                        if not isinstance(cmd, StateCmd):
                            logger.info(cmd)
                        await callback(cmd)
                    except ValidationError:
                        # traceback.print_exc()
                        logger.debug(f"RX: {data}")
                        await callback(ConsoleLog(line=data))
                    except Exception:
                        # Never let a callback exception (e.g. a WebSocket
                        # send on a half-closed socket) kill the read loop
                        # and silently freeze the serial client.
                        logger.exception("Error in serial callback, continuing")
                else:
                    logger.debug(f"RX: {data}")
