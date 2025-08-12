import logging
from fastapi import WebSocket
from protocol import Command, ResetCmd, StateCmd
from serial_client import DebugSerialClient

logger = logging.getLogger(__name__)

class Plumbing:
    def __init__(self):
        self.headlights = False
        self.connections: list[WebSocket] = []
        self.serial = DebugSerialClient()
        self.serial.callback = self.handle_circuitpy_msg

    async def init(self):
        print("connecting serial")
        await self.serial.connect()

    async def shutdown(self):
        pass

    def ws_connect(self, ws: WebSocket):
        self.connections.append(ws)
        logger.info(f"Websocket client connected. Total: {len(self.connections)}")

    def ws_disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        logger.info(f"Gamepad WebSocket disconnected. Total: {len(self.connections)}")

    async def handle_circuitpy_msg(self, msg: Command):
        j = msg.model_dump_json()
        logger.debug("forwarding")
        for ws in self.connections:
            await ws.send_text(j)

    async def button_pressed(self, index, value):
        match index:
            case 0:  # A
                pass
            case 1:  # B
                await self.serial.write_cmd(ResetCmd())
