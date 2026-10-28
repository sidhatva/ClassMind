// Real-Time Dashboard Controller for Multimodal Attendance & Engagement Agent

let chartInstance = null;
const maxDataPoints = 30;
const chartLabels = [];
const engData = [];
const poseData = [];
const audioData = [];
let knownSuggestionIds = new Set();

document.addEventListener('DOMContentLoaded', () => {
  initChart();
  initControls();
  startTelemetryPolling();
});

// 1. Initialize Chart.js
function initChart() {
  const ctx = document.getElementById('engagement-chart').getContext('2d');
  
  // Initialize with empty data slots
  for (let i = 0; i < maxDataPoints; i++) {
    chartLabels.push('');
    engData.push(null);
    poseData.push(null);
    audioData.push(null);
  }

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Overall Engagement',
          data: engData,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 0
        },
        {
          label: 'Head Pose (Attention)',
          data: poseData,
          borderColor: '#38bdf8',
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.3
        },
        {
          label: 'Audio Activity',
          data: audioData,
          borderColor: '#fbbf24',
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
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#6b7280', font: { size: 10 } }
        },
        x: {
          display: false
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// 2. Control Buttons (Simulator & Privacy Mode)
function initControls() {
  const simBtn = document.getElementById('toggle-sim-btn');
  const simIndicator = document.getElementById('sim-indicator');
  const privacyBtn = document.getElementById('toggle-privacy-btn');
  const privacyIndicator = document.getElementById('privacy-indicator');

  let isSimActive = true;
  let isPrivacyActive = false;

  simBtn.addEventListener('click', async () => {
    isSimActive = !isSimActive;
    await postSettings({ use_simulation: isSimActive });
    simIndicator.innerText = isSimActive ? 'Simulator Active' : 'Live Camera Active';
    simBtn.classList.toggle('btn-primary', !isSimActive);
  });

  privacyBtn.addEventListener('click', async () => {
    isPrivacyActive = !isPrivacyActive;
    await postSettings({ anonymize_faces: isPrivacyActive });
    privacyIndicator.innerText = isPrivacyActive ? 'Privacy: Face Blur' : 'Privacy: Normal';
    privacyBtn.classList.toggle('btn-primary', isPrivacyActive);
  });
}

async function postSettings(payload) {
  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (err) {
    console.error('Failed to update settings:', err);
  }
}

// 3. Telemetry Polling Loop
function startTelemetryPolling() {
  setInterval(async () => {
    try {
      const response = await fetch('/api/telemetry');
      if (!response.ok) return;
      const data = await response.json();
      updateDashboard(data);
    } catch (e) {
      // transient network wait
    }
  }, 750);
}

function updateDashboard(data) {
  const t = data.telemetry || {};
  const a = data.attendance || {};
  const i = data.interaction || {};
  const s = data.latest_suggestion;

  // 1. Update KPI Values & Bars
  const engVal = t.overall_engagement !== undefined ? Math.round(t.overall_engagement) : '--';
  const poseVal = t.head_pose_score !== undefined ? Math.round(t.head_pose_score) : '--';
  const motionVal = t.movement_score !== undefined ? Math.round(t.movement_score) : '--';
  const audioVal = t.audio_score !== undefined ? Math.round(t.audio_score) : '--';

  document.getElementById('kpi-engagement').innerText = engVal;
  document.getElementById('engagement-bar').style.width = `${engVal}%`;

  document.getElementById('kpi-head-pose').innerText = poseVal;
  document.getElementById('head-pose-bar').style.width = `${poseVal}%`;

  document.getElementById('kpi-movement').innerText = motionVal;
  document.getElementById('movement-bar').style.width = `${motionVal}%`;

  document.getElementById('kpi-audio').innerText = audioVal;
  document.getElementById('audio-bar').style.width = `${audioVal}%`;

  // Trend Pill
  const trendEl = document.getElementById('trend-indicator');
  const trend = t.trend || 'Steady';
  trendEl.innerText = trend;
  trendEl.className = 'trend-pill ' + trend.toLowerCase();

  // Sub Badges
  document.getElementById('audio-state').innerText = t.is_speech ? 'Active Speech' : 'Silence';
  document.getElementById('speech-ratio-label').innerText = `Talk Ratio: ${Math.round((i.talk_ratio || 0) * 100)}%`;

  // 2. Update Scenario 2 Chart
  if (chartInstance && t.overall_engagement !== undefined) {
    chartLabels.push('');
    engData.push(t.overall_engagement);
    poseData.push(t.head_pose_score);
    audioData.push(t.audio_score);

    if (chartLabels.length > maxDataPoints) {
      chartLabels.shift();
      engData.shift();
      poseData.shift();
      audioData.shift();
    }
    chartInstance.update();
  }

  // 3. Update Scenario 1 Attendance Table
  updateAttendanceTable(a);

  // 4. Update Scenario 3 AI Suggestions
  if (s && s.id && !knownSuggestionIds.has(s.id)) {
    knownSuggestionIds.add(s.id);
    addSuggestionCard(s);
  }
}

function updateAttendanceTable(attendanceData) {
  const statEl = document.getElementById('attendance-stat');
  if (attendanceData.present_count !== undefined) {
    statEl.innerText = `${attendanceData.present_count} / ${attendanceData.total_enrolled} Present (${attendanceData.attendance_rate}%)`;
  }

  const tbody = document.getElementById('attendance-tbody');
  const roster = attendanceData.roster || [];
  if (roster.length === 0) return;

  tbody.innerHTML = '';
  roster.forEach(r => {
    const tr = document.createElement('tr');
    
    let statusClass = 'status-absent';
    if (r.status === 'Present') statusClass = 'status-present';
    else if (r.status === 'Partial') statusClass = 'status-partial';
    else if (r.status === 'Pending') statusClass = 'status-pending';

    tr.innerHTML = `
      <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;">${r.roll_no}</td>
      <td style="font-weight: 600;">${r.name}</td>
      <td><span class="status-tag ${statusClass}">${r.status}</span></td>
      <td>${r.sustained_seconds}s</td>
      <td>${r.presence_ratio}%</td>
    `;
    tbody.appendChild(tr);
  });
}

function addSuggestionCard(s) {
  const container = document.getElementById('suggestions-container');
  const placeholder = container.querySelector('.suggestion-placeholder');
  if (placeholder) placeholder.remove();

  const card = document.createElement('div');
  card.className = `suggestion-card ${s.severity || 'info'}`;
  card.innerHTML = `
    <div class="suggestion-header">
      <span class="suggestion-title">${escapeHtml(s.title)}</span>
      <span class="suggestion-time">${s.timestamp || ''}</span>
    </div>
    <div class="suggestion-body">${escapeHtml(s.suggestion)}</div>
    <div class="suggestion-rationale">Rationale: ${escapeHtml(s.rationale)}</div>
  `;
  container.prepend(card);
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
