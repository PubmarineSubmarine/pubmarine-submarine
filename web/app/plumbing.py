import logging
from asyncio import create_task, sleep
from os import environ

from fastapi import WebSocket
from gpio import reset_pico
from protocol import (
    Command,
    ConsoleLog,
    MotionCmd,
    PingCmd,
    StateCmd,
    StopCmd,
)
from serial_client import DebugSerialClient, SerialClient
from orientation import OrientationEstimator

logger = logging.getLogger(__name__)


class Plumbing:
    def __init__(self):
        self.connections: list[WebSocket] = []
        port = environ.get("SERIAL_PORT")
        if port == "DEBUG":
            self.serial = DebugSerialClient()
        else:
            self.serial = SerialClient(port=port)
        # self.serial = SerialClient("/dev/pts/13", baudrate=9600)
        self.serial.callback = self.handle_circuitpy_msg
        self.throttle = 0.0
        self.steer = 0.0
        self.lights = False
        # Madgwick-based absolute orientation estimator. Runs over every STAT
        # message and emits synthetic ORI messages at 10 Hz, even when the
        # serial stream is slow.
        self.orientation = OrientationEstimator()
        self._ori_task = None
        self._last_ori_emit_ts: float = 0.0

    async def init(self):
        print("connecting serial")
        await self.serial.connect()
        if self._ori_task is None:
            self._ori_task = create_task(self._orientation_loop())

    async def shutdown(self):
        await self.serial.write_cmd(StopCmd())
        self.serial.disconnect()
        if self._ori_task is not None:
            self._ori_task.cancel()
            self._ori_task = None

    def ws_connect(self, ws: WebSocket):
        self.connections.append(ws)
        logger.info(f"Websocket client connected. Total: {len(self.connections)}")

    async def ws_disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        logger.info(f"Gamepad WebSocket disconnected. Total: {len(self.connections)}")
        await self.serial.write_cmd(StopCmd())

    async def handle_circuitpy_msg(self, msg: Command):
        if isinstance(msg, StateCmd):
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    msg.pi = int(f.read().strip()) / 1000.0
                if msg.lights == 1:
                    self.lights = True
                elif msg.lights == 0:
                    self.lights = False
            except:
                pass
            # Feed the orientation filter with the latest accel/gyro. The
            # estimator is rate-limited internally; we just integrate every
            # sample and let the loop below decide when to emit.
            self.orientation.on_state(msg.acc, msg.gyro)
        j = msg.model_dump_json()
        for ws in self.connections:
            await ws.send_text(j)

    async def _orientation_loop(self):
        """Background task that drives the orientation estimator."""
        try:
            while True:
                ori = self.orientation.maybe_emit()
                if ori is not None:
                    j = ori.model_dump_json()
                    for ws in list(self.connections):
                        try:
                            await ws.send_text(j)
                        except Exception:
                            pass
                await sleep(0.02)  # 50 Hz tick
        except Exception:
            logger.exception("orientation loop crashed")

    async def console_cmd(self, text: str):
        stripped = text.strip().upper()
        if stripped == "CAL":
            if self.orientation.calibrate():
                line = "calibrated: current pose is now home (ORI = 0,0,0)"
            else:
                line = "calibration failed: filter not ready yet"
            await self.handle_circuitpy_msg(ConsoleLog(level="ORI", line=line))
            return
        await self.handle_circuitpy_msg(ConsoleLog(level="ECHO", line=text))
        await self.serial.write_text(f"{text}\r\n")

    async def stick_moved(self, stick: str, x: float, y: float):
        if stick == "right":
            # sv1 = int(90 + 45*y)
            # sv2 = int(90 - 45*y)
            # await self.serial.write_cmd(MotionCmd(sv1=sv1, sv2=sv2))
            self.throttle = -y
            await self.update_motors()
        elif stick == "left":
            self.steer = x
            await self.update_motors()

    async def trigger_moved(self, trigger: str, value: float):
        # if trigger == "left":
        #     self.throttle = -value
        #     await self.update_motors()
        # elif trigger == "right":
        #     self.throttle = value
        #     await self.update_motors()
        if trigger == "left":
            sv1 = int(90 + 45 * value)
            sv2 = int(90 - 45 * value)
            await self.serial.write_cmd(MotionCmd(sv1=sv1, sv2=sv2))
        elif trigger == "right":
            sv1 = int(90 - 45 * value)
            sv2 = int(90 + 45 * value)
            await self.serial.write_cmd(MotionCmd(sv1=sv1, sv2=sv2))

    async def update_motors(self):
        a_steer = self.steer
        b_steer = -self.steer
        if abs(self.steer) + abs(self.throttle) > 0:
            rel_steer = abs(self.steer) / (abs(self.steer) + abs(self.throttle))
            rel_throttle = abs(self.throttle) / (abs(self.steer) + abs(self.throttle))
        else:
            rel_steer = 0
            rel_throttle = 1
        a = a_steer * rel_steer + self.throttle * rel_throttle
        b = b_steer * rel_steer + self.throttle * rel_throttle
        print(f"{self.steer=} {self.throttle=} {rel_steer=} {rel_throttle=} {a=} {b=}")
        await self.serial.write_cmd(MotionCmd(a=a, b=b))

    async def button_pressed(self, index, value):
        match index:
            case 0:  # A
                await self.serial.write_cmd(MotionCmd(fu=1, fd=1, fl=1, fr=1, ru=1, rd=1, rl=1, rr=1))
            case 1:  # B
                # await self.serial.write_cmd(ResetCmd())
                self.lights = not self.lights
                await self.serial.write_cmd(MotionCmd(lights=int(self.lights)))
            case 2:  # X
                await self.serial.write_cmd(StopCmd())
            case 3:  # Y
                # await self.serial.write_cmd(MotionCmd(sv1=90, sv2=90))
                pass
            case 4:  # Left Bumper
                # roll CCW
                await self.serial.write_cmd(MotionCmd(fu=1, fr=0, fd=1, fl=0, ru=1, rr=0, rd=1, rl=0))
            case 5:  # Right Bumper
                # roll CW
                await self.serial.write_cmd(MotionCmd(fu=0, fr=1, fd=0, fl=1, ru=0, rr=1, rd=0, rl=1))
            case 12:  # D-Pad Up
                # pitch up
                await self.serial.write_cmd(MotionCmd(fu=1, fr=1, fd=0, fl=0, ru=0, rr=0, rd=1, rl=1))
            case 13:  # D-Pad Down
                # pitch down
                await self.serial.write_cmd(MotionCmd(fu=0, fr=0, fd=1, fl=1, ru=1, rr=1, rd=0, rl=0))
            case 14:  # D-Pad Left
                # yaw left
                await self.serial.write_cmd(MotionCmd(fu=1, fr=0, fd=0, fl=1, ru=0, rr=1, rd=1, rl=0))
            case 15:  # D-Pad Right
                # yaw right
                await self.serial.write_cmd(MotionCmd(fu=0, fr=1, fd=1, fl=0, ru=1, rr=0, rd=0, rl=1))
            case 8:  # back / select
                await reset_pico()
                # await self.serial.write_cmd(ResetCmd(flags=["SOFT"]))

    async def button_released(self, index, value):
        match index:
            case 0:  # A
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 4:  # Left Bumper
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 5:  # Right Bumper
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 12:  # D-Pad Up
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 13:  # D-Pad Down
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 14:  # D-Pad Left
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 15:  # D-Pad Right
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))

    async def heartbeat(self):
        await self.serial.write_cmd(PingCmd())

    async def stop(self):
        await self.serial.write_cmd(StopCmd())
