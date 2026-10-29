# ClassMind AI — System Architecture & Engineering Blueprint

> **ClassMind AI**: Smarter Classrooms. Better Insights. Privacy First.

---

## 1. High-Level Architecture Overview

ClassMind AI is an edge-first, offline-capable smart classroom intelligence platform designed to assist instructors in real time. It combines:

1. **Temporal Sustained Attendance Engine**: Filters out transient glances and passersby using temporal sliding window verification.
2. **Multimodal Classroom Engagement Engine**: Non-intrusively tracks visual head pose proxies, movement dynamics, and acoustic activity, renormalizing weights dynamically when sensors are missing.
3. **Pedagogical Copilot Advisor**: Evaluates aggregate dynamics to generate explainable, non-intrusive teaching suggestions with hysteresis and cooldown deduplication.
4. **Deterministic Synthetic Classroom Simulator**: Allows thorough demonstration and testing without physical cameras or microphones.

```
                              ┌───────────────────────────────────┐
                              │     Physical Devices / Simulator  │
                              │   Webcam (OpenCV) + Mic (PyAudio) │
                              │   OR Deterministic Sim Lab        │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │  ClassroomPipeline (Sync / Queue) │
                              └─────┬───────────┬───────────┬─────┘
                                    │           │           │
                    ┌───────────────┘           │           └──────────────┐
                    ▼                           ▼                          ▼
     ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
     │ Vision & Tracking      │  │ Audio & Interaction    │  │ Attendance Machine     │
     │ - Haar Face Detection  │  │ - VAD RMS Energy       │  │ - Sliding Window (15s) │
     │ - Centroid & IoU Track │  │ - Speech/Silence Ratio │  │ - Sustained Ratio (60%)│
     │ - Head Pose Gaze Proxy │  │ - Monologue Measurement│  │ - Occlusion Tolerance  │
     │ - Optical Frame Motion │  │ - Dynamic Renorm       │  │ - Late/Early Dep Flags │
     │ - Optional Face Match  │  │ - Acoustic Modes       │  │ - Manual Audit Trail   │
     └──────────────┬─────────┘  └──────────┬─────────────┘  └──────────┬─────────────┘
                    │                       │                           │
                    └───────────────────────┼───────────────────────────┘
                                            ▼
                              ┌───────────────────────────────────┐
                              │   Multimodal Engagement Engine    │
                              │   - Normalized Fusion Formula     │
                              │   - Dynamic Weight Renorm         │
                              │   - Rolling Trend & Coverage      │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
                              ┌───────────────────────────────────┐
                              │     Teaching Copilot Agent        │
                              │   - Pedagogical Heuristics        │
                              │   - Cooldown Deduplication        │
                              │   - Feedback Loop (Helpful/Dismiss│
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
                    ┌───────────────────────────┴───────────────────────────┐
                    │                                                       │
                    ▼                                                       ▼
       ┌────────────────────────┐                              ┌────────────────────────┐
       │   SQLite Local Store   │                              │   FastAPI & Dashboard  │
       │   - Sessions & Roster  │                              │   - REST API Endpoints │
       │   - Attendance Records │                              │   - Low-Latency WS     │
       │   - Telemetry Samples  │                              │   - MJPEG Stream Feed  │
       │   - Copilot Suggestions│                              │   - Glassmorphism UI   │
       │   - Audit Logs & Event │                              │   - CSV/JSON Reports   │
       └────────────────────────┘                              └────────────────────────┘
```

---

## 2. Core Subsystems

### A. Temporal Sustained Attendance Engine (`src/attendance/sustained_presence.py`)
- Employs a sliding observation window ($W = 15.0\text{ s}$) with a presence threshold ratio ($R = 0.60$).
- Transient pedestrians walking past a classroom doorway register for $< 2\text{ s}$ and are categorized as **Unverified**.
- Students who maintain active presence $\ge 60\%$ in the sliding window and accumulate $\ge 8.0\text{ s}$ of visual detection transition to **Present**.
- Supports **Present**, **Partial**, **Absent**, and **Unverified** states.
- Late arrivals are automatically flagged if detected after the configured session threshold ($t > 300\text{ s}$).
- Early departures are flagged if a student, previously verified as Present, is absent for $> 60\text{ s}$.
- Instructors can manually override attendance with an explicit audit reason stored in `audit_logs`.

### B. Computer Vision Pipeline (`src/vision/`)
- **Face Tracking**: Uses OpenCV frontal face cascades with an IoU tracker to maintain stable integer track IDs (`#1`, `#2`, etc.) across frame boundaries.
- **Visual Attentiveness**: Measures facial symmetry and eye-level offset to estimate head orientation (yaw and pitch in degrees) as an experimental visual attention proxy.
- **Motion Dynamics**: Regional frame differencing with Gaussian blur inside the upper torso bounding box to quantify movement (taking notes, raising hands, or lethargic slumber).
- **Face Anonymization**: Bounding boxes can be blurred using a $31\times31$ Gaussian kernel in real time (`config.privacy.anonymize_faces = True`).

### C. Audio & VAD Pipeline (`src/audio/`)
- Captures microphone audio in 0.5-second bounded chunks at $16\text{ kHz}$.
- Computes Root Mean Square (RMS) energy to detect speech intervals against ambient background noise.
- Quantifies talk ratio, continuous monologue duration, and classroom silence intervals.
- If physical microphone hardware is unavailable, the pipeline marks `sensor_available: false` and the fusion engine renormalizes without penalizing metrics.

### D. Multimodal Engagement Engine (`src/fusion/engagement_engine.py`)
- Standard multimodal formula:
  $$\text{Composite Score} = \left( w_{\text{head}} \cdot S_{\text{head}} + w_{\text{motion}} \cdot S_{\text{motion}} + w_{\text{audio}} \cdot S_{\text{audio}} \right) \times 100$$
- Default weights: $w_{\text{head}} = 0.45$, $w_{\text{motion}} = 0.25$, $w_{\text{audio}} = 0.30$.
- **Dynamic Renormalization**: If any sensor becomes unavailable (e.g. camera is disconnected or microphone errors), weights are dynamically redistributed over the active sensors:
  $$w'_i = \frac{w_i}{\sum_{j \in \text{active}} w_j}$$
- Trends are calculated over a rolling window of recent observations: **Rising**, **Steady**, **Declining**, or **Insufficient Data**.

### E. AI-Driven Teaching Copilot (`src/agent/teaching_advisor.py`)
- Evaluates classroom signals and generates actionable pedagogical alerts:
  - `ATTENTION_DROP`: Sustained visual deviation $> 12\text{ s}$ across $> 40\%$ of participants.
  - `MONOLOGUE_PACING`: Continuous speech $> 90\text{ s}$ without student interaction.
  - `HIGH_INTERACTION`: High discussion energy with synchronized vocal activity.
  - `LOW_ACTIVITY`: Low movement and extended silence $> 18\text{ s}$.
  - `SENSOR_QUALITY_ISSUE`: Multimodal signal coverage $< 60\%$.
- Prevents repetitive spam using configurable cooldown periods ($20\text{ s}$).
- Includes instructor feedback loops (`is_dismissed`, `is_helpful`).

### F. Deterministic Simulation Mode (`src/simulation/classroom_simulator.py`)
- Generates a synthetic classroom with dynamic avatars demonstrating note-taking, attentive gaze, and diverted postures.
- Models arrival schedules, early departures, and pedagogical phases (monologue, interactive Q&A, attention drop).
- Uses a fixed random seed (`seed=42`) for 100% reproducible testing.
