/**
 * ClassMind AI — Master Dashboard Controller.
 * Handles WebSocket streaming with polling fallback, 7 distinct operational views,
 * real-time Chart.js rendering, manual attendance corrections, and settings synchronization.
 */

// Global State
let chartInstance = null;
let maxDataPoints = 30;
const chartLabels = [];
const engSeries = [];
const poseSeries = [];
const motionSeries = [];
const audioSeries = [];

let activeSessionId = "SESSION-LIVE-01";
let sessionStartEpoch = Date.now();
let knownSuggestionIds = new Set();
let cachedAttendanceRoster = [];
let telemetrySocket = null;
let pollingInterval = null;
let currentCopilotFilter = "ALL";
let editingStudentId = null;

// Video Stream Controller State
let currentActiveViewId = "view-overview";
let currentIsSim = true;
let lastFrameArrivalTs = 0;
let streamFrameArrivals = 0;
let streamWatchdogInterval = null;
let streamConnectTs = 0;

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initVideoStreamController();
  initChart();
  initSessionControls();
  initAttendanceControls();
  initSettingsControls();
  initModals();
  startLiveStreaming();
  loadInitialData();
});

// ==========================================================================
// 1. Navigation & View Switching
// ==========================================================================
function initNavigation() {
  const navButtons = document.querySelectorAll(".nav-item");
  navButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetView = btn.getAttribute("data-view");
      switchView(targetView);
    });
  });
}

function switchView(viewId) {
  // Update nav buttons
  document.querySelectorAll(".nav-item").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-view") === viewId);
  });

  // Update panels
  document.querySelectorAll(".view-panel").forEach(p => {
    p.classList.toggle("active", p.id === viewId);
  });

  // Handle active video stream transitions
  handleStreamViewChange(viewId);

  // Trigger view-specific refreshes
  if (viewId === "view-history") {
    loadSessionHistory();
  } else if (viewId === "view-attendance") {
    refreshAttendanceTable();
  } else if (viewId === "view-settings") {
    loadSettingsData();
  } else if (viewId === "view-copilot") {
    loadAllRecommendations();
  }
}

// ==========================================================================
// 1b. Real-Time Video Stream Controller & Lifecycle Manager
// ==========================================================================
function initVideoStreamController() {
  const mainStream = document.getElementById("live-main-stream");
  const overviewStream = document.getElementById("overview-video-feed");
  const loadingOverlay = document.getElementById("video-stream-loading");
  const errorOverlay = document.getElementById("video-stream-error");
  const reconnectBtn = document.getElementById("btn-reconnect-stream");

  if (reconnectBtn) {
    reconnectBtn.addEventListener("click", () => {
      reconnectLiveStream();
    });
  }

  if (mainStream) {
    mainStream.addEventListener("load", () => {
      if (loadingOverlay) loadingOverlay.classList.add("hidden");
      if (errorOverlay) errorOverlay.classList.add("hidden");
      lastFrameArrivalTs = Date.now();
      streamFrameArrivals++;

      const statusEl = document.getElementById("video-feed-status");
      const dotEl = document.getElementById("video-feed-status-dot");
      if (statusEl) {
        statusEl.innerText = `Stream Active • ${currentIsSim ? 'Simulation' : 'Hardware Camera'}`;
      }
      if (dotEl) {
        dotEl.className = "badge-dot pulse";
      }

      if (mainStream.naturalWidth > 0) {
        const resStr = `${mainStream.naturalWidth}x${mainStream.naturalHeight}`;
        const resTag = document.getElementById("live-tag-res");
        const resBadge = document.getElementById("live-stream-res-badge");
        if (resTag) resTag.innerText = resStr;
        if (resBadge) resBadge.innerText = resStr;
      }
    });

    mainStream.addEventListener("error", () => {
      console.warn("[ClassMind AI] Live main video stream error or disconnected.");
      if (currentActiveViewId === "view-live") {
        if (loadingOverlay) loadingOverlay.classList.add("hidden");
        if (errorOverlay) errorOverlay.classList.remove("hidden");
        const statusEl = document.getElementById("video-feed-status");
        const dotEl = document.getElementById("video-feed-status-dot");
        if (statusEl) statusEl.innerText = "Stream Disconnected • Waiting to reconnect";
        if (dotEl) dotEl.className = "badge-dot dot-error";
      }
    });
  }

  // Initial stream setup for default active view
  handleStreamViewChange(currentActiveViewId);

  // Stream health & watchdog timer (every 1 second)
  if (streamWatchdogInterval) clearInterval(streamWatchdogInterval);
  streamWatchdogInterval = setInterval(() => {
    if (currentActiveViewId === "view-live" && mainStream) {
      const now = Date.now();
      const timeSinceConnect = now - streamConnectTs;
      const isLoaded = mainStream.complete && mainStream.naturalWidth > 0;

      if (isLoaded) {
        if (loadingOverlay) loadingOverlay.classList.add("hidden");
        if (errorOverlay) errorOverlay.classList.add("hidden");
        const statusEl = document.getElementById("video-feed-status");
        const dotEl = document.getElementById("video-feed-status-dot");
        if (statusEl) {
          statusEl.innerText = `Stream Active • ${currentIsSim ? 'Simulation' : 'Hardware Camera'}`;
        }
        if (dotEl) dotEl.className = "badge-dot pulse";
      } else if (timeSinceConnect > 4500) {
        // Stream timed out with no valid frames decoded
        if (loadingOverlay) loadingOverlay.classList.add("hidden");
        if (errorOverlay) errorOverlay.classList.remove("hidden");
        const statusEl = document.getElementById("video-feed-status");
        const dotEl = document.getElementById("video-feed-status-dot");
        if (statusEl) statusEl.innerText = "Stream Inactive • No Frames Received";
        if (dotEl) dotEl.className = "badge-dot dot-error";
      }
    }
  }, 1000);
}

function handleStreamViewChange(viewId) {
  currentActiveViewId = viewId;
  const mainStream = document.getElementById("live-main-stream");
  const overviewStream = document.getElementById("overview-video-feed");
  const loadingOverlay = document.getElementById("video-stream-loading");
  const errorOverlay = document.getElementById("video-stream-error");

  if (viewId === "view-live") {
    // Disconnect overview stream to avoid duplicate stream contention
    if (overviewStream) overviewStream.src = "";

    // Connect main stream with dedicated live identifier & cache buster
    if (mainStream) {
      if (loadingOverlay) loadingOverlay.classList.remove("hidden");
      if (errorOverlay) errorOverlay.classList.add("hidden");
      streamConnectTs = Date.now();
      const statusEl = document.getElementById("video-feed-status");
      const dotEl = document.getElementById("video-feed-status-dot");
      if (statusEl) statusEl.innerText = "Connecting to real-time stream...";
      if (dotEl) dotEl.className = "badge-dot";

      mainStream.src = `/video_feed?stream=live&t=${Date.now()}`;
    }
  } else if (viewId === "view-overview") {
    // Disconnect main live stream
    if (mainStream) mainStream.src = "";

    // Connect overview stream
    if (overviewStream && (!overviewStream.src || overviewStream.src === "")) {
      overviewStream.src = `/video_feed?stream=overview&t=${Date.now()}`;
    }
  } else {
    // In background views, detach streams to preserve resources
    if (mainStream) mainStream.src = "";
    if (overviewStream) overviewStream.src = "";
  }
}

function reconnectLiveStream() {
  const mainStream = document.getElementById("live-main-stream");
  const loadingOverlay = document.getElementById("video-stream-loading");
  const errorOverlay = document.getElementById("video-stream-error");

  if (loadingOverlay) loadingOverlay.classList.remove("hidden");
  if (errorOverlay) errorOverlay.classList.add("hidden");
  streamConnectTs = Date.now();

  const statusEl = document.getElementById("video-feed-status");
  const dotEl = document.getElementById("video-feed-status-dot");
  if (statusEl) statusEl.innerText = "Reconnecting stream...";
  if (dotEl) dotEl.className = "badge-dot";

  if (mainStream) {
    mainStream.src = "";
    setTimeout(() => {
      mainStream.src = `/video_feed?stream=live&t=${Date.now()}`;
    }, 150);
  }
}

// ==========================================================================
// 2. Real-Time Telemetry Streaming (WebSocket with HTTP Polling Fallback)
// ==========================================================================
function startLiveStreaming() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

  try {
    telemetrySocket = new WebSocket(wsUrl);

    telemetrySocket.onopen = () => {
      console.log("[ClassMind AI] WebSocket connection established.");
      if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }
    };

    telemetrySocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleTelemetryUpdate(data);
      } catch (err) {
        console.error("Error parsing telemetry message:", err);
      }
    };

    telemetrySocket.onerror = () => {
      console.warn("[ClassMind AI] WebSocket error, starting polling fallback...");
      startPollingFallback();
    };

    telemetrySocket.onclose = () => {
      console.warn("[ClassMind AI] WebSocket closed, starting polling fallback...");
      startPollingFallback();
    };
  } catch (e) {
    startPollingFallback();
  }
}

function startPollingFallback() {
  if (pollingInterval) return;
  pollingInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/telemetry");
      if (res.ok) {
        const data = await res.json();
        handleTelemetryUpdate(data);
      }
    } catch (e) {
      // transient network wait
    }
  }, 750);
}

// ==========================================================================
// 3. Telemetry Dispatcher & UI Synchronizer
// ==========================================================================
function handleTelemetryUpdate(data) {
  if (!data) return;

  const t = data.telemetry || {};
  const a = data.attendance || {};
  const i = data.interaction || {};
  const participants = data.participants || [];
  const s = data.latest_suggestion;
  const isSim = data.use_simulation;
  const isPaused = data.is_paused;

  // Header Status
  updateHeaderStatus(isPaused, isSim);

  // View A: Overview KPIs
  updateOverviewView(t, a, i, data.fps, data.latency_ms);

  // View B: Live Classroom HUD
  updateLiveClassroomView(participants, isSim, data.fps, data.latency_ms, data.camera_error);

  // View C: Attendance Cache & Table
  if (a.records) {
    cachedAttendanceRoster = a.records;
    renderAttendanceRows();
  }

  // View D: Analytics Time-Series Chart
  updateChartData(t);

  // View E: Copilot Recommendations
  if (s && s.id && !knownSuggestionIds.has(s.id)) {
    knownSuggestionIds.add(s.id);
    prependRecommendation(s);
    showToast(`Teaching Alert: ${s.title}`, "info");
  }
}

function updateHeaderStatus(isPaused, isSim) {
  const statusBadge = document.getElementById("header-session-status");
  const statusText = document.getElementById("session-status-text");
  const pauseBtn = document.getElementById("btn-pause-session");
  const resumeBtn = document.getElementById("btn-resume-session");
  const modeBadge = document.getElementById("header-mode-badge");

  if (isPaused) {
    statusBadge.className = "session-status-badge status-paused";
    statusText.innerText = "PAUSED";
    pauseBtn.classList.add("hidden");
    resumeBtn.classList.remove("hidden");
  } else {
    statusBadge.className = "session-status-badge status-live";
    statusText.innerText = "LIVE SESSION";
    pauseBtn.classList.remove("hidden");
    resumeBtn.classList.add("hidden");
  }

  modeBadge.innerText = isSim ? "Simulation Mode" : "Physical Camera";
  modeBadge.className = isSim ? "chip chip-mode" : "chip";

  // Duration counter
  const elapsedSec = Math.floor((Date.now() - sessionStartEpoch) / 1000);
  const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, '0');
  const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, '0');
  const secs = String(elapsedSec % 60).padStart(2, '0');
  document.getElementById("header-session-duration").innerText = `${hrs}:${mins}:${secs}`;
}

function updateOverviewView(t, a, i, fps, latency) {
  // Engagement KPI
  const engVal = t.overall_engagement !== undefined ? Math.round(t.overall_engagement) : "--";
  document.getElementById("overview-engagement-val").innerText = engVal;
  document.getElementById("overview-engagement-bar").style.width = `${engVal}%`;

  const trendEl = document.getElementById("kpi-trend");
  const trend = t.trend || "Steady";
  trendEl.innerText = trend;
  trendEl.className = "trend-pill " + trend.toLowerCase().replace(" ", "-");

  // Attendance Counts
  if (a.present_count !== undefined) {
    document.getElementById("overview-attendance-rate").innerText = `${a.attendance_rate}%`;
    document.getElementById("overview-present-cnt").innerText = a.present_count;
    document.getElementById("overview-partial-cnt").innerText = a.partial_count;
    document.getElementById("overview-absent-cnt").innerText = a.absent_count;
    document.getElementById("overview-unverified-cnt").innerText = a.unverified_count || 0;
    document.getElementById("overview-enrolled-summary").innerText = `Enrolled: ${a.total_enrolled} Students`;
  }

  // Visual Pose Proxy
  const poseVal = t.head_pose_score !== null && t.head_pose_score !== undefined ? Math.round(t.head_pose_score) : "--";
  document.getElementById("overview-pose-val").innerText = poseVal;
  document.getElementById("overview-pose-bar").style.width = `${poseVal}%`;

  // Audio Activity
  const audioVal = t.audio_score !== null && t.audio_score !== undefined ? Math.round(t.audio_score) : "--";
  document.getElementById("overview-audio-val").innerText = audioVal;
  document.getElementById("overview-audio-bar").style.width = `${audioVal}%`;
  document.getElementById("overview-audio-state").innerText = t.is_speech ? "Active Speech" : "Silent";
  document.getElementById("overview-talk-ratio-label").innerText = `Talk Ratio: ${Math.round((i.talk_ratio || 0) * 100)}%`;

  // Mini HUD Stream Info
  if (fps !== undefined) {
    document.getElementById("mini-stream-fps").innerText = `${fps} FPS`;
    document.getElementById("mini-stream-latency").innerText = `${latency}ms`;
  }
}

function updateLiveClassroomView(participants, isSim, fps, latency, cameraError) {
  currentIsSim = isSim;
  const sourceLabel = isSim ? "Source: Simulation" : "Source: Camera (Hardware)";
  document.getElementById("live-tag-source").innerText = sourceLabel;
  document.getElementById("live-participant-count").innerText = `${participants.length} Tracked`;

  const tagFps = document.getElementById("live-tag-fps");
  if (tagFps && fps !== undefined) tagFps.innerText = `FPS: ${fps}`;

  const hudFps = document.getElementById("live-stream-fps-badge");
  if (hudFps && fps !== undefined) hudFps.innerText = `${fps} FPS`;

  const hudLatency = document.getElementById("live-stream-latency-badge");
  if (hudLatency && latency !== undefined) hudLatency.innerText = `${latency}ms`;

  const hudRes = document.getElementById("live-stream-res-badge");
  const mainStream = document.getElementById("live-main-stream");
  if (hudRes && mainStream && mainStream.naturalWidth > 0) {
    const resText = `${mainStream.naturalWidth}x${mainStream.naturalHeight}`;
    hudRes.innerText = resText;
    document.getElementById("live-tag-res").innerText = resText;
  }

  // Update hardware indicator in sidebar footer
  const camDot = document.getElementById("cam-status-dot");
  const camText = document.getElementById("cam-status-text");
  if (camText) {
    camText.innerText = isSim ? "Simulation Active" : "Webcam Live";
  }
  if (camDot) {
    camDot.className = "sensor-indicator sensor-live";
  }

  // If there was a camera initialization error
  if (cameraError && isSim) {
    const errorEl = document.getElementById("video-error-text");
    if (errorEl && currentActiveViewId === "view-live" && (!mainStream || !mainStream.complete)) {
      errorEl.innerText = cameraError;
    }
  }

  const container = document.getElementById("live-participants-container");
  if (!participants || participants.length === 0) {
    container.innerHTML = `<div class="empty-state">No face tracks currently detected in camera view.</div>`;
    return;
  }

  container.innerHTML = "";
  participants.forEach(p => {
    const card = document.createElement("div");
    card.className = "participant-card";

    let badgeClass = "badge-attentive";
    if (p.state.includes("Down") || p.state.includes("Notes")) badgeClass = "badge-down";
    else if (p.state.includes("Away") || p.state.includes("Inattentive")) badgeClass = "badge-away";

    card.innerHTML = `
      <div class="participant-card-header">
        <span class="participant-name">#${p.track_id} ${escapeHtml(p.display_name)}</span>
        <span class="participant-badge ${badgeClass}">${escapeHtml(p.state)}</span>
      </div>
      <div class="participant-metrics">
        <span>Attn: ${Math.round(p.attentiveness_score * 100)}%</span>
        <span>Motion: ${Math.round(p.motion_score * 100)}%</span>
        <span>${p.is_inactive ? 'Inactive (' + p.inactivity_seconds + 's)' : 'Active'}</span>
      </div>
    `;
    container.appendChild(card);
  });
}

// ==========================================================================
// 4. Analytics Chart.js Initialization & Timeline
// ==========================================================================
function initChart() {
  const ctx = document.getElementById("analytics-timeseries-chart").getContext("2d");

  for (let i = 0; i < maxDataPoints; i++) {
    chartLabels.push("");
    engSeries.push(null);
    poseSeries.push(null);
    motionSeries.push(null);
    audioSeries.push(null);
  }

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: "Overall Engagement",
          data: engSeries,
          borderColor: "#6366f1",
          backgroundColor: "rgba(99, 102, 241, 0.12)",
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 0
        },
        {
          label: "Visual Attention",
          data: poseSeries,
          borderColor: "#06b6d4",
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: "Movement Dynamics",
          data: motionSeries,
          borderColor: "#10b981",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: "Audio Activity",
          data: audioSeries,
          borderColor: "#f59e0b",
          borderWidth: 1.5,
          borderDash: [2, 2],
          pointRadius: 0,
          fill: false,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { size: 10 } }
        },
        x: { display: false }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#161e2e",
          titleColor: "#fff",
          bodyColor: "#94a3b8"
        }
      }
    }
  });

  // Chart range buttons
  document.querySelectorAll(".btn-chart-range").forEach(b => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".btn-chart-range").forEach(btn => btn.classList.remove("active"));
      b.classList.add("active");
      maxDataPoints = parseInt(b.getAttribute("data-points"), 10);
      trimChartSeries();
    });
  });
}

function updateChartData(t) {
  if (!chartInstance || t.overall_engagement === undefined) return;

  chartLabels.push("");
  engSeries.push(t.overall_engagement);
  poseSeries.push(t.head_pose_score);
  motionSeries.push(t.movement_score);
  audioSeries.push(t.audio_score);

  trimChartSeries();
  chartInstance.update();

  // Dynamic weight breakdown update in View D
  if (t.formula_contribution) {
    const c = t.formula_contribution;
    const container = document.getElementById("analytics-weights-breakdown");
    container.innerHTML = `
      <div class="weight-row">
        <div class="weight-row-label"><span>Visual Head Pose</span><span>${c.head_pose}</span></div>
        <div class="progress-track"><div class="progress-bar bar-cyan" style="width: ${c.head_pose}"></div></div>
      </div>
      <div class="weight-row">
        <div class="weight-row-label"><span>Physical Movement</span><span>${c.movement}</span></div>
        <div class="progress-track"><div class="progress-bar" style="width: ${c.movement}"></div></div>
      </div>
      <div class="weight-row">
        <div class="weight-row-label"><span>Acoustic Energy</span><span>${c.audio}</span></div>
        <div class="progress-track"><div class="progress-bar bar-amber" style="width: ${c.audio}"></div></div>
      </div>
    `;
  }

  // Coverage badge
  if (t.sensor_coverage !== undefined) {
    const cov = Math.round(t.sensor_coverage * 100);
    document.getElementById("coverage-percentage-badge").innerText = `${cov}%`;
    document.getElementById("sensor-coverage-details").innerText = `${cov}% Sensory Coverage (${t.active_sensors ? t.active_sensors.join(", ") : 'None'})`;
  }
}

function trimChartSeries() {
  while (chartLabels.length > maxDataPoints) {
    chartLabels.shift();
    engSeries.shift();
    poseSeries.shift();
    motionSeries.shift();
    audioSeries.shift();
  }
}

// ==========================================================================
// 5. Attendance Management & Overrides
// ==========================================================================
function initAttendanceControls() {
  const searchInput = document.getElementById("attendance-search");
  const filterSelect = document.getElementById("attendance-filter-status");

  searchInput.addEventListener("input", renderAttendanceRows);
  filterSelect.addEventListener("change", renderAttendanceRows);

  document.getElementById("btn-view-audit-logs").addEventListener("click", loadAuditLogs);
}

function refreshAttendanceTable() {
  fetch(`/api/attendance/summary?session_id=${activeSessionId}`)
    .then(r => r.json())
    .then(data => {
      if (data.records) {
        cachedAttendanceRoster = data.records;
        renderAttendanceRows();
      }
    })
    .catch(console.error);
}

function renderAttendanceRows() {
  const tbody = document.getElementById("attendance-table-body");
  if (!tbody) return;

  const search = document.getElementById("attendance-search").value.toLowerCase();
  const filter = document.getElementById("attendance-filter-status").value;

  tbody.innerHTML = "";

  const filtered = cachedAttendanceRoster.filter(r => {
    const matchesSearch = r.name.toLowerCase().includes(search) || r.roll_no.toLowerCase().includes(search);
    const matchesFilter = filter === "ALL" || r.status === filter;
    return matchesSearch && matchesFilter;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-dim); padding: 2rem;">No matching attendance records found.</td></tr>`;
    return;
  }

  filtered.forEach(r => {
    const tr = document.createElement("tr");

    let statusPillClass = "absent";
    if (r.status === "Present") statusPillClass = "present";
    else if (r.status === "Partial") statusPillClass = "partial";
    else if (r.status === "Unverified") statusPillClass = "unverified";

    // Flags
    let flagsHtml = "";
    if (r.is_late) flagsHtml += `<span class="tag-flag tag-late">Late</span> `;
    if (r.is_early_departure) flagsHtml += `<span class="tag-flag tag-early">Early Dep.</span> `;
    if (r.manual_correction) flagsHtml += `<span class="tag-flag" style="background: rgba(99,102,241,0.2); color: #818cf8;">Manual</span>`;
    if (!flagsHtml) flagsHtml = "-";

    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-size: 0.8rem;">${escapeHtml(r.roll_no)}</td>
      <td style="font-weight: 600; color: #fff;">${escapeHtml(r.name)}</td>
      <td>${escapeHtml(r.section || 'Section A')}</td>
      <td><span class="status-pill ${statusPillClass}">${escapeHtml(r.status)}</span></td>
      <td>${r.sustained_seconds}s</td>
      <td>${r.presence_ratio}%</td>
      <td>${Math.round(r.confidence * 100)}%</td>
      <td>${flagsHtml}</td>
      <td style="font-size: 0.75rem; color: var(--text-muted); max-width: 220px;">${escapeHtml(r.verification_reason)}</td>
      <td>
        <button class="btn btn-xs btn-secondary" onclick="openCorrectionModal('${r.student_id}', '${escapeHtml(r.name)}', '${escapeHtml(r.roll_no)}', '${r.status}')">
          Edit
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function openCorrectionModal(studentId, name, rollNo, currentStatus) {
  editingStudentId = studentId;
  document.getElementById("modal-student-name").innerText = name;
  document.getElementById("modal-student-roll").innerText = rollNo;
  document.getElementById("modal-select-status").value = currentStatus;
  document.getElementById("modal-input-reason").value = "";
  openModal("modal-correction");
}

async function submitAttendanceCorrection() {
  if (!editingStudentId) return;

  const newStatus = document.getElementById("modal-select-status").value;
  const reason = document.getElementById("modal-input-reason").value.trim();

  if (!reason) {
    showToast("Please provide an audit explanation for this override.", "error");
    return;
  }

  try {
    const res = await fetch("/api/attendance/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_id: editingStudentId,
        new_status: newStatus,
        reason: reason,
        instructor_id: "Instructor"
      })
    });

    if (res.ok) {
      showToast("Attendance updated successfully.", "success");
      closeModal("modal-correction");
      refreshAttendanceTable();
    } else {
      showToast("Failed to update attendance.", "error");
    }
  } catch (err) {
    showToast("Network error submitting correction.", "error");
  }
}

async function loadAuditLogs() {
  try {
    const res = await fetch(`/api/attendance/audit-trail?session_id=${activeSessionId}`);
    if (res.ok) {
      const logs = await res.json();
      const tbody = document.getElementById("audit-trail-tbody");
      tbody.innerHTML = "";
      if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">No manual overrides recorded for this session.</td></tr>`;
      } else {
        logs.forEach(l => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td style="font-family: var(--font-mono); font-size: 0.75rem;">${escapeHtml(l.timestamp)}</td>
            <td>${escapeHtml(l.student_id)}</td>
            <td><span class="status-pill">${escapeHtml(l.previous_status)}</span></td>
            <td><span class="status-pill present">${escapeHtml(l.new_status)}</span></td>
            <td>${escapeHtml(l.changed_by)}</td>
            <td style="font-size: 0.78rem;">${escapeHtml(l.reason)}</td>
          `;
          tbody.appendChild(tr);
        });
      }
      openModal("modal-audit-trail");
    }
  } catch (err) {
    showToast("Failed to fetch audit trail.", "error");
  }
}

// ==========================================================================
// 6. Teaching Copilot Recommendations
// ==========================================================================
function prependRecommendation(s) {
  // Add to Overview view
  const overviewContainer = document.getElementById("overview-copilot-container");
  const emptyEl = overviewContainer.querySelector(".empty-state");
  if (emptyEl) emptyEl.remove();

  const miniCard = document.createElement("div");
  miniCard.className = `recommendation-card ${s.priority || 'info'}`;
  miniCard.innerHTML = `
    <div class="rec-header">
      <span class="rec-title">${escapeHtml(s.title)}</span>
      <span class="rec-time">${s.timestamp || ''}</span>
    </div>
    <div class="rec-suggestion">${escapeHtml(s.suggestion)}</div>
  `;
  overviewContainer.prepend(miniCard);

  // Add to View E Copilot view
  const copilotContainer = document.getElementById("copilot-recommendations-list");
  const fullCard = document.createElement("div");
  fullCard.className = `recommendation-card ${s.priority || 'info'}`;
  fullCard.id = `rec-card-${s.id}`;
  fullCard.innerHTML = `
    <div class="rec-header">
      <div class="rec-title-group">
        <span class="rec-badge ${s.priority || 'info'}">${escapeHtml(s.priority || 'INFO')}</span>
        <span class="rec-title">${escapeHtml(s.title)}</span>
      </div>
      <span class="rec-time">${s.timestamp || ''}</span>
    </div>
    <div class="rec-suggestion">${escapeHtml(s.suggestion)}</div>
    <div class="rec-details-grid">
      <div class="rec-rationale"><strong>Trigger:</strong> ${escapeHtml(s.triggering_signal || s.rationale)}</div>
      <div class="rec-purpose"><strong>Purpose:</strong> ${escapeHtml(s.instructional_purpose || 'Instructional support')}</div>
    </div>
    <div class="rec-actions">
      <button class="btn btn-xs btn-secondary" onclick="handleRecFeedback(${s.id}, false, true)">Helpful</button>
      <button class="btn btn-xs btn-secondary" onclick="handleRecFeedback(${s.id}, true, null)">Dismiss</button>
    </div>
  `;
  copilotContainer.prepend(fullCard);

  // Update badge count in sidebar
  const countBadge = document.getElementById("nav-rec-count");
  countBadge.innerText = parseInt(countBadge.innerText || "0", 10) + 1;
}

async function loadAllRecommendations() {
  try {
    const res = await fetch(`/api/recommendations?session_id=${activeSessionId}`);
    if (res.ok) {
      const list = await res.json();
      const container = document.getElementById("copilot-recommendations-list");
      container.innerHTML = "";
      if (list.length === 0) {
        container.innerHTML = `<div class="empty-state">No active recommendations. Classroom signals are within expected thresholds.</div>`;
      } else {
        list.forEach(s => prependRecommendation(s));
      }
    }
  } catch (err) {
    console.error("Failed to load recommendations:", err);
  }
}

async function handleRecFeedback(recId, isDismissed, isHelpful) {
  try {
    await fetch(`/api/recommendations/${recId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_dismissed: isDismissed, is_helpful: isHelpful })
    });

    if (isDismissed) {
      const el = document.getElementById(`rec-card-${recId}`);
      if (el) el.remove();
      showToast("Recommendation dismissed.", "info");
    } else if (isHelpful) {
      showToast("Feedback recorded: Marked as helpful.", "success");
    }
  } catch (err) {
    console.error("Failed to post feedback:", err);
  }
}

// ==========================================================================
// 7. Session History & Archives
// ==========================================================================
async function loadSessionHistory() {
  try {
    const res = await fetch("/api/sessions?limit=50");
    if (res.ok) {
      const sessions = await res.json();
      const tbody = document.getElementById("sessions-history-tbody");
      tbody.innerHTML = "";

      if (sessions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 2rem;">No previous sessions recorded.</td></tr>`;
        return;
      }

      sessions.forEach(s => {
        const tr = document.createElement("tr");
        const statusBadge = s.is_active ? `<span class="status-pill present">Active</span>` : `<span class="status-pill unverified">Completed</span>`;

        tr.innerHTML = `
          <td style="font-family: var(--font-mono); font-size: 0.78rem;">${escapeHtml(s.session_id)}</td>
          <td style="font-weight: 600; color: #fff;">${escapeHtml(s.title)}</td>
          <td>${escapeHtml(s.section)}</td>
          <td>${escapeHtml(s.instructor_name)}</td>
          <td style="font-size: 0.75rem;">${escapeHtml(s.start_time)}</td>
          <td>${s.total_enrolled}</td>
          <td style="font-weight: 600; color: var(--accent-emerald);">${s.total_present}</td>
          <td>${statusBadge}</td>
          <td>
            <a href="/api/attendance/export/csv?session_id=${s.session_id}" class="btn btn-xs btn-secondary" download>CSV</a>
            <a href="/api/attendance/export/json?session_id=${s.session_id}" class="btn btn-xs btn-secondary" download>JSON</a>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error("Failed to load session history:", err);
  }
}

// ==========================================================================
// 8. Settings & Privacy Controls
// ==========================================================================
function initSettingsControls() {
  const saveBtn = document.getElementById("btn-save-settings");
  saveBtn.addEventListener("click", saveSettingsData);

  document.getElementById("btn-prune-retention").addEventListener("click", async () => {
    const days = parseInt(document.getElementById("set-retention-days").value, 10) || 30;
    try {
      const res = await fetch(`/api/settings/retention/prune?days=${days}`, { method: "POST" });
      const data = await res.json();
      showToast(`Pruned ${data.sessions_pruned} sessions older than ${days} days.`, "success");
    } catch (e) {
      showToast("Failed to prune retention records.", "error");
    }
  });

  document.getElementById("btn-backup-db").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/settings/backup", { method: "POST" });
      const data = await res.json();
      showToast(`Snapshot created: ${data.backup_file.split('\\').pop()}`, "success");
    } catch (e) {
      showToast("Failed to create database snapshot.", "error");
    }
  });

  // Slider numerical mirrors
  const sHead = document.getElementById("slider-weight-head");
  const sMotion = document.getElementById("slider-weight-motion");
  const sAudio = document.getElementById("slider-weight-audio");

  sHead.addEventListener("input", () => document.getElementById("val-weight-head").innerText = sHead.value);
  sMotion.addEventListener("input", () => document.getElementById("val-weight-motion").innerText = sMotion.value);
  sAudio.addEventListener("input", () => document.getElementById("val-weight-audio").innerText = sAudio.value);

  // Quick blur button in top header
  document.getElementById("btn-quick-privacy").addEventListener("click", togglePrivacyBlur);
  document.getElementById("btn-toggle-blur-live").addEventListener("click", togglePrivacyBlur);

  // Toggle Camera Source in View B
  document.getElementById("btn-toggle-camera-src").addEventListener("click", async () => {
    const isSimNow = document.getElementById("live-tag-source").innerText.includes("Simulation");
    const nextSim = !isSimNow;

    const statusEl = document.getElementById("video-feed-status");
    if (statusEl) {
      statusEl.innerText = nextSim ? "Activating Simulation Mode..." : "Initializing Physical Camera...";
    }
    const loadingOverlay = document.getElementById("video-stream-loading");
    if (loadingOverlay) loadingOverlay.classList.remove("hidden");
    const errorOverlay = document.getElementById("video-stream-error");
    if (errorOverlay) errorOverlay.classList.add("hidden");

    try {
      await postSettingsUpdate({ use_simulation: nextSim });
      showToast(nextSim ? "Simulation Mode Activated" : "Connecting to Physical Camera...", "info");
      setTimeout(reconnectLiveStream, 350);
    } catch (err) {
      showToast("Failed to switch source: " + err.message, "error");
      reconnectLiveStream();
    }
  });
}

async function loadSettingsData() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const s = await res.json();
      document.getElementById("set-privacy-blur").checked = s.anonymize_faces;
      document.getElementById("set-biometric-matching").checked = s.biometric_matching_enabled;
      document.getElementById("set-retention-days").value = s.data_retention_days;
      document.getElementById("set-window-duration").value = s.window_duration_seconds;
      document.getElementById("set-presence-ratio").value = s.sustained_presence_ratio;

      document.getElementById("slider-weight-head").value = s.weight_head_pose;
      document.getElementById("val-weight-head").innerText = s.weight_head_pose;

      document.getElementById("slider-weight-motion").value = s.weight_movement;
      document.getElementById("val-weight-motion").innerText = s.weight_movement;

      document.getElementById("slider-weight-audio").value = s.weight_audio_activity;
      document.getElementById("val-weight-audio").innerText = s.weight_audio_activity;

      updatePrivacyBadge(s.anonymize_faces);
    }
  } catch (err) {
    console.error("Failed to load settings:", err);
  }
}

async function saveSettingsData() {
  const payload = {
    anonymize_faces: document.getElementById("set-privacy-blur").checked,
    biometric_matching_enabled: document.getElementById("set-biometric-matching").checked,
    data_retention_days: parseInt(document.getElementById("set-retention-days").value, 10),
    window_duration_seconds: parseFloat(document.getElementById("set-window-duration").value),
    sustained_presence_ratio: parseFloat(document.getElementById("set-presence-ratio").value),
    weight_head_pose: parseFloat(document.getElementById("slider-weight-head").value),
    weight_movement: parseFloat(document.getElementById("slider-weight-motion").value),
    weight_audio_activity: parseFloat(document.getElementById("slider-weight-audio").value)
  };

  await postSettingsUpdate(payload);
  showToast("System configuration saved.", "success");
}

async function postSettingsUpdate(payload) {
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      if (data.anonymize_faces !== undefined) {
        updatePrivacyBadge(data.anonymize_faces);
      }
    }
  } catch (err) {
    console.error("Settings update error:", err);
  }
}

async function togglePrivacyBlur() {
  const headerLabel = document.getElementById("header-privacy-label");
  const liveTag = document.getElementById("live-tag-anon");
  const isCurrentlyOn = (headerLabel && headerLabel.innerText.includes("On")) ||
                        (liveTag && liveTag.innerText.includes("Active"));
  const next = !isCurrentlyOn;
  await postSettingsUpdate({ anonymize_faces: next });
  updatePrivacyBadge(next);
  showToast(`Privacy Face Blurring ${next ? 'Enabled' : 'Disabled'}`, "info");
}

function updatePrivacyBadge(isOn) {
  const label = document.getElementById("header-privacy-label");
  const liveTag = document.getElementById("live-tag-anon");
  if (label) label.innerText = isOn ? "Blur: On" : "Blur: Off";
  if (liveTag) liveTag.innerText = isOn ? "Privacy: Active (Blur)" : "Privacy: Normal";
  const checkbox = document.getElementById("set-privacy-blur");
  if (checkbox) checkbox.checked = isOn;
}

// ==========================================================================
// 9. Session Controls & Modals
// ==========================================================================
function initSessionControls() {
  document.getElementById("btn-pause-session").addEventListener("click", async () => {
    await fetch("/api/sessions/current/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "pause" })
    });
    showToast("Monitoring paused.", "info");
  });

  document.getElementById("btn-resume-session").addEventListener("click", async () => {
    await fetch("/api/sessions/current/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "resume" })
    });
    showToast("Monitoring resumed.", "success");
  });

  document.getElementById("btn-stop-session").addEventListener("click", async () => {
    if (confirm("Are you sure you want to stop and finalize this classroom session?")) {
      await fetch("/api/sessions/current/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop" })
      });
      showToast("Session stopped and finalized.", "info");
    }
  });

  document.getElementById("btn-new-session-modal").addEventListener("click", () => {
    openModal("modal-new-session");
  });

  document.getElementById("btn-submit-new-session").addEventListener("click", async () => {
    const title = document.getElementById("new-session-title").value.trim();
    const section = document.getElementById("new-session-section").value.trim();
    const instructor = document.getElementById("new-session-instructor").value.trim();
    const enrolled = parseInt(document.getElementById("new-session-enrolled").value, 10) || 6;

    if (!title) {
      showToast("Please enter a session title.", "error");
      return;
    }

    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title,
          section: section,
          instructor_name: instructor,
          total_enrolled: enrolled
        })
      });

      if (res.ok) {
        const newSession = await res.json();
        activeSessionId = newSession.session_id;
        sessionStartEpoch = Date.now();
        document.getElementById("header-session-title").innerText = newSession.title;
        document.getElementById("header-session-id").innerText = `ID: ${newSession.session_id}`;
        closeModal("modal-new-session");
        showToast(`Started new session: ${newSession.title}`, "success");
        refreshAttendanceTable();
      }
    } catch (e) {
      showToast("Failed to create new session.", "error");
    }
  });
}

function initModals() {
  document.getElementById("btn-submit-correction").addEventListener("click", submitAttendanceCorrection);
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("active");
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function loadInitialData() {
  refreshAttendanceTable();
  loadAllRecommendations();
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
