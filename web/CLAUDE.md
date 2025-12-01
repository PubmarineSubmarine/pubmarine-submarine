# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based web server for controlling a submarine via gamepad. The system runs on a Raspberry Pi and interfaces with CircuitPython hardware over serial communication. It provides real-time gamepad control through WebSockets and proxies camera feeds from a MediaMTX server.

## Running the Application

**Development (local):**
```bash
uv run app/main.py
```

The server will start on port 8000. If SSL certificates exist in `certs/cert.pem` and `certs/key.pem`, it will use HTTPS, otherwise HTTP.

**Production (systemd service):**
```bash
sudo systemctl start missioncontrol
sudo systemctl status missioncontrol
sudo systemctl restart missioncontrol
```

Service configuration is located at `/etc/systemd/system/missioncontrol.service`

## Architecture

### Core Components

**app/main.py** - FastAPI application entry point
- Handles WebSocket connections for gamepad input at `/ws/gamepad`
- Proxies camera endpoints from MediaMTX server (localhost:8889) to `/cam/*`
- Manages application lifecycle via `plumbing_lifespan` context manager
- Initializes GPIO and serial connections on startup

**app/plumbing.py** - Business logic orchestrator
- Maps gamepad events to submarine control commands
- Manages WebSocket connections for broadcasting submarine state
- Translates stick/trigger movements to motor and servo commands
- Button mapping:
  - A (0): Set servos to test position (0°/180°)
  - B (1): Send RESET command to CircuitPython
  - X (2): Send STOP command (emergency stop)
  - Y (3): Center servos (90°/90°)
  - Back/Select (8): Hardware reset Pico via GPIO

**app/serial_client.py** - Serial communication manager
- Auto-reconnecting serial client for CircuitPython hardware (default: `/dev/ttyACM0` at 115200 baud)
- Continuous read loop parses incoming STATE commands
- Handles connection failures with automatic retry logic
- Includes `DebugSerialClient` for testing without hardware

**app/protocol.py** - Command protocol definitions
- Pydantic models for submarine commands with serialization/deserialization
- Command types:
  - `RESET`: Reset submarine controller
  - `STOP`: Emergency stop all motors
  - `MOT`: Motion command (x/z translation, servo angles, thruster states)
  - `STAT`: State report from submarine (position, sensors, battery)
- Commands serialize to text format: `MOT X=1.0 Z=-0.5 SV1=90 FU=1 RD=1`

**app/gpio.py** - Raspberry Pi GPIO control
- Manages GPIO pin 18 for Pico hardware reset
- Gracefully handles absence of GPIO (for development on non-Pi systems)

### Communication Flow

1. Browser connects via WebSocket to `/ws/gamepad`
2. JavaScript gamepad API sends events (buttons, sticks, triggers) as JSON
3. `main.py` routes events to `plumbing.py` handlers
4. `plumbing.py` translates events to protocol commands
5. `serial_client.py` sends commands to CircuitPython hardware
6. Incoming STATE messages from hardware are broadcast back to all connected WebSockets

### Frontend

- **templates/gamepad.html**: Main control interface with live gamepad visualization
- **static/js/gamepad.js**: Gamepad API integration, sends events to WebSocket
- **static/css/gamepad.css**: Gamepad visualization styling

## Dependencies

Python dependencies are managed via `uv` (pyproject.toml):
- FastAPI + Uvicorn for web server
- Jinja2 for templates
- pyserial-asyncio for serial communication
- RPi.GPIO for hardware control (Pi only)
- httpx for proxying MediaMTX camera server
- Pydantic for command validation

## Related Services

**MediaMTX** - Camera streaming server
- Runs on localhost:8889
- Endpoints proxied through FastAPI at `/cam/*`
- Configuration: `configs/mediamtx.yml`
- Systemd service: `mediamtx`

## Hardware Interface

The system expects CircuitPython hardware connected via USB serial that:
- Accepts text-based commands (MOT, RESET, STOP)
- Periodically sends STAT commands with telemetry
- Can be hardware-reset via GPIO pin 18 on Raspberry Pi

## Development Notes

- Serial port can be configured in `plumbing.py` (`SerialClient` initialization)
- Use `DebugSerialClient` for testing without hardware (uncomment in `plumbing.py`)
- SSL certificates in `certs/` directory enable HTTPS (optional)
- WebSocket accepts gamepad events: `button_press`, `button_release`, `analog_stick`, `analog_trigger`
