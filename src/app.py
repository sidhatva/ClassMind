"""
FastAPI Web Application & Real-Time Intelligence Server.
Provides video streaming, REST APIs for telemetry & attendance,
and the interactive instructor dashboard.
"""

import io
import csv
import time
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config import config, BASE_DIR
from src.database import init_database, seed_default_roster, create_session, get_latest_suggestions, get_session_attendance
from src.pipeline import ClassroomPipeline

app = FastAPI(title="Multimodal Attendance & Engagement Agent")

# Directory paths
UI_DIR = BASE_DIR / "src" / "ui"
STATIC_DIR = UI_DIR / "static"
TEMPLATES_DIR = UI_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Pipeline Singleton
SESSION_ID = "SESSION-LIVE-01"
pipeline: ClassroomPipeline = None


@app.on_event("startup")
def startup_event():
    global pipeline
    init_database()
    seed_default_roster()
    create_session(SESSION_ID, "Lecture 1: Multimodal Intelligence & Edge AI", total_enrolled=6)
    pipeline = ClassroomPipeline(session_id=SESSION_ID, video_source=config.camera_index)
    print("[Server] Multimodal Attendance & Engagement Agent initialized.")


def generate_video_stream():
    """MJPEG frame generator for browser video streaming."""
    while True:
        if pipeline is not None:
            frame_bytes = pipeline.get_jpeg_frame()
            if frame_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
        time.sleep(0.04)  # ~25 FPS


@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"session_id": SESSION_ID})


@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/telemetry")
async def get_telemetry():
    if pipeline is None:
        return JSONResponse({"status": "initializing"})
    
    # Trigger one pipeline step if video_feed is not currently being pulled
    _, output = pipeline.process_frame()
    return JSONResponse(output)


class SettingsPayload(BaseModel):
    use_simulation: bool = None
    anonymize_faces: bool = None


@app.post("/api/settings")
async def update_settings(payload: SettingsPayload):
    if payload.use_simulation is not None and pipeline is not None:
        pipeline.set_simulation_mode(payload.use_simulation)
    if payload.anonymize_faces is not None:
        config.privacy.anonymize_faces = payload.anonymize_faces
    return {"status": "success", "settings": {"simulation": pipeline.use_simulation if pipeline else False, "anonymize": config.privacy.anonymize_faces}}


@app.get("/api/suggestions")
async def get_suggestions():
    suggestions = get_latest_suggestions(SESSION_ID, limit=20)
    return JSONResponse(suggestions)


@app.get("/api/export/attendance")
async def export_attendance():
    """Scenario 1: Exports verified sustained attendance records as CSV."""
    records = get_session_attendance(SESSION_ID)
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV Header
    writer.writerow(["Student ID", "Roll No", "Student Name", "Attendance Status", "Sustained Presence (sec)", "Presence Ratio", "First Detected", "Last Detected"])
    
    for r in records:
        writer.writerow([
            r["student_id"],
            r["roll_no"],
            r["name"],
            r["status"],
            r["sustained_seconds"],
            f"{r['presence_ratio'] * 100:.1f}%",
            r["first_detected"] or "N/A",
            r["last_detected"] or "N/A"
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{SESSION_ID}.csv"}
    )
