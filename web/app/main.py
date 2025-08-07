from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import logging

import httpx

app = FastAPI(title="Pubmarine Submarine", version="0.1.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Set up logging for gamepad data
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections: list[WebSocket] = []


@app.get("/", response_class=HTMLResponse)
async def gamepad_demo(request: Request):
    """Serve the gamepad demo page."""
    return templates.TemplateResponse(
        "gamepad.html", 
        {"request": request}
    )

@app.get("/gamepad")
async def gamepad_page(request: Request):
    # redirect response to /
    """returns a RedirectResponse to hte index at /"""
    return RedirectResponse(
        url="/"
    )


@app.websocket("/ws/gamepad")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time gamepad data."""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"New gamepad WebSocket connection. Total: {len(active_connections)}")
    
    try:
        while True:
            # Receive gamepad data from client
            data = await websocket.receive_text()
            gamepad_data = json.loads(data)
            
            # Log the gamepad data
            log_gamepad_data(gamepad_data)
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"Gamepad WebSocket disconnected. Total: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


def log_gamepad_data(data: dict):
    """Log gamepad data in a readable format."""
    event_type = data.get("type", "unknown")
    
    if event_type == "button_press":
        button_name = data.get("button_name", "Unknown")
        button_value = data.get("value", 0)
        logger.info(f"🎮 BUTTON: {button_name} pressed (value: {button_value:.3f})")
        
    elif event_type == "analog_stick":
        stick = data.get("stick", "unknown")
        x = data.get("x", 0)
        y = data.get("y", 0)
        logger.info(f"🕹️  STICK: {stick} moved to X:{x:.3f}, Y:{y:.3f}")
        
    elif event_type == "gamepad_connected":
        gamepad_id = data.get("gamepad_id", "Unknown")
        logger.info(f"🔌 GAMEPAD CONNECTED: {gamepad_id}")
        
    elif event_type == "gamepad_disconnected":
        logger.info(f"🔌 GAMEPAD DISCONNECTED")
        
    else:
        logger.info(f"🎮 GAMEPAD DATA: {data}")


@app.get("/cam")
async def proxy_cam(request: Request):

    target_url = "http://localhost:8889/cam"
    
    headers = dict(request.headers)
    if "host" in headers:
        del headers["host"]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url=target_url,
            headers=headers,
            params=request.query_params
        )
        
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=response.headers.get("content-type"),
            headers=dict(response.headers)
        )

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
        
    cert_file = Path("certs/cert.pem")
    key_file = Path("certs/key.pem")
    
    if cert_file.exists() and key_file.exists():
        print("Access at: https://localhost:8000")
        print("You may need to accept the self-signed certificate warning.")
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            ssl_keyfile=str(key_file),
            ssl_certfile=str(cert_file)
        )
    else:
        print("Access at: http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)