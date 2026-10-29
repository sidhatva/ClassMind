"""
ClassMind AI - Real-Time Smart Classroom Intelligence Server.
FastAPI Application providing REST APIs, WebSocket streaming, MJPEG video feed,
and responsive instructor dashboard.
"""

import time
import json
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import config, BASE_DIR
from src.database import init_database, seed_default_roster
from src.services.session_manager import SessionManager
from src.api.health import router as health_router
from src.api.sessions import router as sessions_router
from src.api.attendance import router as attendance_router
from src.api.analytics import router as analytics_router
from src.api.recommendations import router as recommendations_router
from src.api.roster import router as roster_router
from src.api.settings import router as settings_router


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[ClassMind AI] Initializing local database and session manager...")
    init_database()
    seed_default_roster()
    session_mgr = SessionManager.get_instance()
    session_mgr.initialize_default_session(force_sim=False)
    print(f"[ClassMind AI] Active Session Initialized: {session_mgr.active_session_id}")

    yield

    # Shutdown
    print("[ClassMind AI] Gracefully shutting down and releasing hardware resources...")
    session_mgr = SessionManager.get_instance()
    session_mgr.stop_current_session()
    print("[ClassMind AI] System offline.")


app = FastAPI(
    title="ClassMind AI",
    description="Privacy-First Multimodal Attendance & Engagement Intelligence Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(attendance_router)
app.include_router(analytics_router)
app.include_router(recommendations_router)
app.include_router(roster_router)
app.include_router(settings_router)

# Mount Static UI assets & Templates
UI_DIR = BASE_DIR / "src" / "ui"
STATIC_DIR = UI_DIR / "static"
TEMPLATES_DIR = UI_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def generate_video_stream():
    """MJPEG frame generator for browser video streaming."""
    session_mgr = SessionManager.get_instance()
    boundary = b"--frame\r\n"
    while True:
        try:
            if session_mgr.pipeline is not None and session_mgr.is_running:
                frame_bytes = session_mgr.pipeline.get_jpeg_frame()
                if frame_bytes:
                    yield (
                        boundary +
                        b"Content-Type: image/jpeg\r\n" +
                        f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode() +
                        frame_bytes +
                        b"\r\n"
                    )
            await asyncio.sleep(0.033)  # ~30 FPS
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.05)


@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    session_mgr = SessionManager.get_instance()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"session_id": session_mgr.active_session_id}
    )


@app.get("/video_feed")
async def video_feed(stream: Optional[str] = None):
    """Live MJPEG video feed endpoint with privacy blurring support."""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close"
        }
    )


@app.get("/api/telemetry")
async def get_telemetry():
    """Polling fallback endpoint for real-time telemetry."""
    session_mgr = SessionManager.get_instance()
    if session_mgr.pipeline is None:
        return JSONResponse({"status": "initializing"})
    
    output = session_mgr.pipeline.get_latest_telemetry()
    return JSONResponse(output)


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Real-time bi-directional WebSocket connection for low-latency dashboard streaming."""
    await ws_manager.connect(websocket)
    session_mgr = SessionManager.get_instance()
    try:
        while True:
            if session_mgr.pipeline is not None:
                output = session_mgr.pipeline.get_latest_telemetry()
                if output:
                    await websocket.send_json(output)
            await asyncio.sleep(0.1)  # ~10Hz
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
