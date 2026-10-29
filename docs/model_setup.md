# ClassMind AI — Model Setup & Hardware Diagnostics Guide

> **ClassMind AI**: Smarter Classrooms. Better Insights. Privacy First.

---

## 1. Computer Vision Models & Dependencies

ClassMind AI utilizes lightweight, battle-tested computer vision algorithms optimized for edge CPUs without requiring heavy GPU clusters or external API tokens.

### 1.1 Built-in Haar Cascades (Default Baseline)
The default vision pipeline relies on OpenCV's built-in Haar Feature-based Cascade Classifiers:
- `haarcascade_frontalface_default.xml`
- `haarcascade_eye.xml`

**Source**: Included automatically in OpenCV (`cv2.data.haarcascades`).  
**License**: BSD 3-Clause (Apache 2.0 compatible).  
**Runtime Path**: Loaded dynamically from `cv2.data.haarcascades`.  
**Resource Overhead**: $< 5\text{ MB}$ RAM, $\approx 12\text{ ms}$ inference latency on standard Intel/AMD/Apple Silicon CPUs.

### 1.2 Optional Landmark Tracking (MediaPipe / ONNX)
For higher-resolution facial landmark tracking:
- Install MediaPipe: `pip install mediapipe`
- The system automatically detects MediaPipe if present and falls back gracefully to OpenCV cascades if unavailable.

---

## 2. Audio Processing & Microphone Setup

### 2.1 PyAudio & Native Sound Card Drivers
- **Windows**: PyAudio uses Windows Audio Session API (WASAPI) or DirectSound.
  ```bash
  pip install pyaudio
  ```
- **Linux (Ubuntu/Debian)**: Requires `portaudio19-dev`:
  ```bash
  sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-pyaudio
  pip install pyaudio
  ```
- **macOS**: Requires `portaudio` via Homebrew:
  ```bash
  brew install portaudio
  pip install pyaudio
  ```

### 2.2 Hardware Failure Recovery
If no physical microphone is attached, PyAudio throws an initialization error. ClassMind AI captures this exception cleanly, marks `microphone_available: false`, and renormalizes multimodal fusion weights to rely exclusively on visual cues without interrupting the session.

---

## 3. Hardware Diagnostics & Troubleshooting

| Diagnostic Symptom | Probable Cause | Recommended Resolution |
|--------------------|----------------|------------------------|
| Camera opens black screen | Permission denied or index mismatch | Pass `--camera 1` or grant camera permissions in OS settings. |
| Microphone silent | Default input device muted | Adjust OS input volume or test via Windows Sound Recorder. |
| Audio VAD silent | Energy threshold too high | Lower `audio_energy_threshold` in `config.py` from `0.03` to `0.015`. |
| High CPU usage | Resolution too high | Default is $640\times480$. Adjust `video_width` and `video_height` in `config.py`. |
| Port 8080 busy | Another process using port | Launch with `--port 8000` or `--port 8081`. |
