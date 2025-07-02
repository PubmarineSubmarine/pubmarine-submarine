from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, List
import json
import logging
import cv2
import threading
import time

app = FastAPI(title="Pubmarine Submarine", version="0.1.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# In-memory counter storage (in production, use a database)
counter_state: Dict[str, int] = {"value": 0}

# Set up logging for gamepad data
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections: List[WebSocket] = []

# Video capture setup
video_capture = None
video_lock = threading.Lock()
latest_frame = None
frame_lock = threading.Lock()
video_thread = None
video_running = False


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main page with HTMX counter demo."""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "counter": counter_state["value"]}
    )


@app.post("/increment")
async def increment_counter(request: Request):
    """HTMX endpoint to increment counter."""
    counter_state["value"] += 1
    return templates.TemplateResponse(
        "counter.html", 
        {"request": request, "counter": counter_state["value"]}
    )


@app.post("/decrement")
async def decrement_counter(request: Request):
    """HTMX endpoint to decrement counter."""
    counter_state["value"] -= 1
    return templates.TemplateResponse(
        "counter.html", 
        {"request": request, "counter": counter_state["value"]}
    )


@app.post("/reset")
async def reset_counter(request: Request):
    """HTMX endpoint to reset counter."""
    counter_state["value"] = 0
    return templates.TemplateResponse(
        "counter.html", 
        {"request": request, "counter": counter_state["value"]}
    )


@app.get("/gamepad", response_class=HTMLResponse)
async def gamepad_demo(request: Request):
    """Serve the gamepad demo page."""
    return templates.TemplateResponse(
        "gamepad.html", 
        {"request": request}
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
            
            # Echo back confirmation (optional)
            await websocket.send_text(json.dumps({"status": "received"}))
            
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


def init_video_capture():
    """Initialize video capture from /dev/video0."""
    global video_capture, video_thread, video_running
    try:
        video_capture = cv2.VideoCapture(0)  # /dev/video0
        if not video_capture.isOpened():
            logger.warning("Could not open /dev/video0")
            video_capture = None
            return False
        
        # Set video properties for better performance
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        video_capture.set(cv2.CAP_PROP_FPS, 30)
        
        # Start video capture thread
        video_running = True
        video_thread = threading.Thread(target=video_capture_loop, daemon=True)
        video_thread.start()
        
        logger.info("📹 Video capture initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize video capture: {e}")
        video_capture = None
        return False


def video_capture_loop():
    """Continuously capture frames in a separate thread."""
    global video_capture, latest_frame, video_running
    
    while video_running:
        if video_capture is None or not video_capture.isOpened():
            # Create black frame with error message
            with frame_lock:
                latest_frame = cv2.imencode('.jpg', 
                    cv2.putText(
                        cv2.zeros((480, 640, 3), dtype=cv2.uint8),
                        "No Video Available",
                        (200, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 255, 255),
                        2
                    )
                )[1].tobytes()
            time.sleep(0.1)
            continue
        
        ret, frame = video_capture.read()
        if ret:
            # Encode frame as JPEG and store
            _, buffer = cv2.imencode('.jpg', frame)
            with frame_lock:
                latest_frame = buffer.tobytes()
        else:
            logger.warning("Failed to read video frame")
        
        time.sleep(1/30)  # ~30 FPS


def generate_video_stream():
    """Generate video frames for streaming from shared frame buffer."""
    global latest_frame
    
    while True:
        with frame_lock:
            if latest_frame is not None:
                frame_bytes = latest_frame
            else:
                # Fallback frame if no data yet
                frame_bytes = cv2.imencode('.jpg', 
                    cv2.putText(
                        cv2.zeros((480, 640, 3), dtype=cv2.uint8),
                        "Loading Video...",
                        (220, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 255, 255),
                        2
                    )
                )[1].tobytes()
        
        # Yield frame in multipart format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(1/30)  # ~30 FPS


@app.get("/video_stream")
async def video_stream():
    """Serve video stream from /dev/video0."""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    import os
    from pathlib import Path
    
    # Initialize video capture
    init_video_capture()
    
    # Check for SSL certificates
    cert_file = Path("certs/cert.pem")
    key_file = Path("certs/key.pem")
    
    if cert_file.exists() and key_file.exists():
        print("Starting HTTPS server (required for Gamepad API)...")
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
        print("Starting HTTP server...")
        print("WARNING: Gamepad API requires HTTPS. Run 'python generate_cert.py' first.")
        print("Access at: http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)