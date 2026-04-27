import logging
from fastapi import WebSocket
from protocol import Command, ResetCmd, StopCmd, MotionCmd, ConsoleLog
from serial_client import DebugSerialClient, SerialClient
from gpio import reset_pico
from os import environ

logger = logging.getLogger(__name__)

class Plumbing:
    def __init__(self):
        self.connections: list[WebSocket] = []
        #self.serial = DebugSerialClient()
        if environ.get("PUBMARINE_DEBUG_SERIAL"):
            self.serial = DebugSerialClient()
        else:
            self.serial = SerialClient("/dev/ttyACM0")
        #self.serial = SerialClient("/dev/pts/13", baudrate=9600)
        self.serial.callback = self.handle_circuitpy_msg

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

    async def console_cmd(self, text: str):
        await self.handle_circuitpy_msg(ConsoleLog(level="ECHO", line=text))
        await self.serial.write_text(repr(f"{text}\r\n"))

    async def stick_moved(self, stick: str, x: float, y: float):
        if stick == "left":
            sv1 = int(90 + 45*y)
            sv2 = int(90 - 45*y)
            await self.serial.write_cmd(MotionCmd(sv1=sv1, sv2=sv2))
        elif stick == "right":
            # Used for the debug impl. No idea what this does to the real sub uncomment at your own risk
            pass
            #if abs(x) > 0.1:
            #    if x < 0:
            #        await self.serial.write_cmd(MotionCmd(fl=1, rl=1))
            #    else:
            #        await self.serial.write_cmd(MotionCmd(fr=1, rr=1))
            #else:
            #    await self.serial.write_cmd(MotionCmd(fl=0, rl=0, fr=0, rr=0))

    async def trigger_moved(self, trigger: str, value: float):
        if trigger == "left":
            await self.serial.write_cmd(MotionCmd(x=-value, z=-value))
        elif trigger == "right":
            await self.serial.write_cmd(MotionCmd(x=value, z=value))

    async def button_pressed(self, index, value):
        match index:
            case 0:  # A
                await self.serial.write_cmd(MotionCmd(sv1=0, sv2=180))
            case 1:  # B
                await self.serial.write_cmd(ResetCmd())
            case 2:  # X
                await self.serial.write_cmd(StopCmd())
            case 3:  # Y
                await self.serial.write_cmd(MotionCmd(sv1=90, sv2=90))
            case 8: # back / select
                await reset_pico()

    async def button_released(self, index, value):
        pass
