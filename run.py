"""
Launch entrypoint for the Multimodal Attendance & Engagement Agent.
Starts the FastAPI application and edge intelligence engine.
"""

import sys
import argparse
import uvicorn
from config import config

def main():
    parser = argparse.ArgumentParser(description="Multimodal Attendance & Engagement Agent")
    parser.add_argument("--host", type=str, default=config.host, help="Host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=config.port, help="Port (default: 8000)")
    parser.add_argument("--camera", type=int, default=config.camera_index, help="Webcam device index (default: 0)")
    parser.add_argument("--sim", action="store_true", help="Force synthetic classroom simulation mode")
    parser.add_argument("--privacy", action="store_true", help="Enable face anonymization/blurring by default")

    args = parser.parse_args()
    config.camera_index = args.camera
    if args.privacy:
        config.privacy.anonymize_faces = True

    print("\n" + "="*70)
    print("   MULTIMODAL ATTENDANCE & ENGAGEMENT AGENT")
    print("   Privacy-Preserving Edge AI Classroom Intelligence System")
    print("="*70)
    print(f" -> System URL:     http://{args.host}:{args.port}")
    print(f" -> Offline Mode:   ENABLED (Zero cloud transmission)")
    print(f" -> Scenario 1:     Automated Sustained Attendance Tracking")
    print(f" -> Scenario 2:     Multimodal Engagement (Head Pose, Motion, VAD)")
    print(f" -> Scenario 3:     AI-Driven Teaching Suggestions Copilot")
    print("="*70 + "\n")

    uvicorn.run("src.app:app", host=args.host, port=args.port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
