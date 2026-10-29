# ClassMind AI — Privacy, Security & Data Protection Charter

> **ClassMind AI**: Smarter Classrooms. Better Insights. Privacy First.

---

## 1. Core Privacy Tenets

ClassMind AI was engineered from the ground up as an offline-first, edge intelligence platform. Privacy is not a feature toggle; it is a foundational architectural principle.

### 1.1 Local Edge Execution
- All computer vision, voice activity detection, multimodal fusion, and recommendation reasoning happen strictly on the local machine.
- Zero frames, video feeds, audio recordings, or biometric embeddings are transmitted across the local network or to third-party cloud services.
- The system operates entirely offline without requiring internet access.

### 1.2 No Raw Media Retention
- Camera frames and audio buffers are processed in transient, bounded memory queues and immediately discarded.
- Raw video frames and raw audio WAV files are **never saved to disk** by default.
- Only timestamped aggregate numerical telemetry (head pose score, movement score, acoustic RMS energy) is retained in the local SQLite database.

### 1.3 Face Anonymization (Blurring by Default)
- Instructors and institutions can enforce full face blurring.
- Detected face regions are blurred using a $31\times31$ Gaussian kernel prior to browser streaming and HUD rendering, ensuring that individual identities are obscured on public classroom displays.

### 1.4 Optional, Consent-Based Biometric Matching
- Biometric identity matching is **disabled by default**.
- When disabled, participants are assigned anonymous sequential tracker IDs (e.g. `Participant #1`, `Track #2`).
- Identity matching can only be enabled after explicit enrollment and institutional authorization.

### 1.5 Explainable Indicators — No Emotion or Mind-Reading
- ClassMind AI measures visual orientation (yaw/pitch) and physical posture movement strictly as **behavioral proxies** for instructional pacing.
- The platform **never claims to read internal student emotions**, cognitive capacity, comprehension, or psychological states from facial expressions or head movements.
- Scores must never be used to automatically penalize, discipline, grade, or evaluate individual students.

---

## 2. Data Retention & Instructor Governance

### 2.1 Configurable Retention Windows
- Instructors can configure data retention periods (default: 30 days) in `Settings & Privacy`.
- Data older than the retention window can be purged at any time via `POST /api/settings/retention/prune` or through the dashboard.

### 2.2 Teacher Review & Audit Trails
- Automated sustained presence attendance is assistive. Instructors have final authority to review and correct any attendance record.
- Every manual override records:
  - Timestamp
  - Previous status
  - Overridden status
  - Changed by (Instructor ID)
  - Detailed audit rationale

---

## 3. Institutional Deployment Checklist

When deploying ClassMind AI in an educational institution, administrators should verify:
1. **Consent & Notice**: Transparent signage informing students that real-time video/audio is processed locally for classroom dynamics with no cloud transmission.
2. **Access Control**: Secure local server endpoints using firewall rules or reverse proxy authentication (Nginx/Caddy with TLS).
3. **Hardware Isolation**: Restrict physical access to the edge device hosting the SQLite database.
