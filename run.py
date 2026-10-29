"""
ClassMind AI - Launch Entrypoint.
Starts the FastAPI application and privacy-preserving edge intelligence engine.
"""

import sys
import argparse
import os
import uvicorn
from config import config

def main():
    parser = argparse.ArgumentParser(description="ClassMind AI - Smart Classroom Intelligence Platform")
    parser.add_argument("--host", type=str, default=config.host, help="Host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=config.port, help="Port (default: 8080)")
    parser.add_argument("--camera", type=int, default=config.camera_index, help="Webcam device index (default: 0)")
    parser.add_argument("--sim", action="store_true", help="Force synthetic classroom simulation mode")
    parser.add_argument("--privacy", action="store_true", help="Enable face anonymization/blurring by default")

    args = parser.parse_args()
    config.camera_index = args.camera
    if args.privacy:
        config.privacy.anonymize_faces = True
    if args.sim:
        os.environ["FORCE_SIMULATION"] = "1"

    print("\n" + "="*75)
    print("   CLASSMIND AI - SMART CLASSROOM INTELLIGENCE PLATFORM")
    print("   Smarter Classrooms. Better Insights. Privacy First.")
    print("="*75)
    print(f" -> System URL:         http://{args.host}:{args.port}")
    print(f" -> Offline Edge Mode:  ENABLED (Zero external cloud calls)")
    print(f" -> Video Source:       {'Synthetic Simulation' if args.sim else f'Camera #{args.camera}'}")
    print(f" -> Privacy Blur:       {'ENABLED (Faces Anonymized)' if config.privacy.anonymize_faces else 'Standard'}")
    print(f" -> Module 1:           Temporal Sustained Attendance Tracking")
    print(f" -> Module 2:           Multimodal Engagement & Interaction Dynamics")
    print(f" -> Module 3:           AI Teaching Suggestions Copilot")
    print("="*75 + "\n")

    uvicorn.run("src.app:app", host=args.host, port=args.port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
