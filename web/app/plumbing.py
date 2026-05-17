import logging
from fastapi import WebSocket
from protocol import Command, ResetCmd, StopCmd, MotionCmd
from serial_client import SerialClient
from gpio import reset_pico

logger = logging.getLogger(__name__)

class Plumbing:
    def __init__(self):
        self.connections: list[WebSocket] = []
        #self.serial = DebugSerialClient()
        self.serial = SerialClient("/dev/ttyACM0")
        #self.serial = SerialClient("/dev/pts/13", baudrate=9600)
        self.serial.callback = self.handle_circuitpy_msg
        self.throttle = 0.0
        self.steer = 0.0

    async def init(self):
        print("connecting serial")
        await self.serial.connect()

    async def shutdown(self):
        await self.serial.write_cmd(StopCmd())
        await self.serial.disconnect()

    def ws_connect(self, ws: WebSocket):
        self.connections.append(ws)
        logger.info(f"Websocket client connected. Total: {len(self.connections)}")

    def ws_disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        logger.info(f"Gamepad WebSocket disconnected. Total: {len(self.connections)}")

    async def handle_circuitpy_msg(self, msg: Command):
        j = msg.model_dump_json()
        for ws in self.connections:
            await ws.send_text(j)

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
            sv1 = int(90 + 45*value)
            sv2 = int(90 - 45*value)
            await self.serial.write_cmd(MotionCmd(sv1=sv1, sv2=sv2))
        elif trigger == "right":
            sv1 = int(90 - 45*value)
            sv2 = int(90 + 45*value)
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
        # TODO motors are swapped
        await self.serial.write_cmd(MotionCmd(a=a, b=b))

    async def button_pressed(self, index, value):
        match index:
            case 0:  # A
                await self.serial.write_cmd(MotionCmd(sv1=0, sv2=180))
            case 1:  # B
                # await self.serial.write_cmd(ResetCmd())
                pass
            case 2:  # X
                await self.serial.write_cmd(StopCmd())
            case 3:  # Y
                await self.serial.write_cmd(MotionCmd(sv1=90, sv2=90))
            case 4:  # Left Bumper
                # roll CCW
                await self.serial.write_cmd(MotionCmd(fu=1, fr=0, fd=1, fl=0, ru=1, rr=0, rd=1, rl=0))
            case 5:  # Right Bumper
                # roll CW
                await self.serial.write_cmd(MotionCmd(fu=0, fr=1, fd=0, fl=1, ru=0, rr=1, rd=0, rl=1))
            case 12: # D-Pad Up
                # pitch up
                await self.serial.write_cmd(MotionCmd(fu=1, fr=1, fd=0, fl=0, ru=0, rr=0, rd=1, rl=1))
            case 13: # D-Pad Down
                # pitch down
                await self.serial.write_cmd(MotionCmd(fu=0, fr=0, fd=1, fl=1, ru=1, rr=1, rd=0, rl=0))
            case 14: # D-Pad Left
                # yaw left
                await self.serial.write_cmd(MotionCmd(fu=1, fr=0, fd=0, fl=1, ru=0, rr=1, rd=1, rl=0))
            case 15: # D-Pad Right
                # yaw right
                await self.serial.write_cmd(MotionCmd(fu=0, fr=1, fd=1, fl=0, ru=1, rr=0, rd=0, rl=1))
            case 8: # back / select
                #await reset_pico()
                await self.serial.write_cmd(ResetCmd(flags=["SOFT"]))

    async def button_released(self, index, value):
        match index:
            case 4:  # Left Bumper
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 5:  # Right Bumper
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 12: # D-Pad Up
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 13: # D-Pad Down
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 14: # D-Pad Left
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
            case 15: # D-Pad Right
                await self.serial.write_cmd(MotionCmd(fu=0, fd=0, fl=0, fr=0, ru=0, rd=0, rl=0, rr=0))
