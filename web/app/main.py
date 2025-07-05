from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import logging
import cv2
import threading
import time
import numpy as np

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

# Video capture setup
video_capture = None
latest_frame = None
frame_lock = threading.Lock()
video_thread = None
video_running = False

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


def generate_error_frame(message: str):
    """Generate a black frame with an error message."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Calculate text size to center the message
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    thickness = 2
    text_size, _ = cv2.getTextSize(message, font, font_scale, thickness)
    text_width, text_height = text_size
    x = (frame.shape[1] - text_width) // 2
    y = (frame.shape[0] + text_height) // 2
    cv2.putText(frame, message, (x, y), font, font_scale, (255, 255, 255), thickness)
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()

def video_capture_loop():
    """Continuously capture frames in a separate thread."""
    global video_capture, latest_frame, video_running
    
    while video_running:
        if video_capture is None or not video_capture.isOpened():
            # Create black frame with error message
            with frame_lock:
                latest_frame = generate_error_frame("No Video")
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
        
        time.sleep(1/30)


def generate_video_stream():
    """Generate video frames for streaming from shared frame buffer."""
    global latest_frame
    
    while True:
        with frame_lock:
            if latest_frame is not None:
                frame_bytes = latest_frame
            else:
                # Fallback frame if no data yet
                frame_bytes = generate_error_frame("No Video")
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(1 / 30)


@app.get("/video_stream")
async def video_stream():
    """Serve video stream from /dev/video0."""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    
    init_video_capture()
    
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