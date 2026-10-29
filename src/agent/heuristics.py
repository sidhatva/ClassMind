"""
ClassMind AI - Pedagogical Heuristics and Recommendation Rules Catalog.
Maps multi-sensor engagement and interaction signals to deterministic, explainable teaching suggestions.
Never claims to read internal emotions, thoughts, or cognitive potential.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TeachingRule:
    alert_type: str
    priority: str  # 'info', 'warning', 'urgent'
    title: str
    suggestion: str
    rationale: str
    instructional_purpose: str


RULES_CATALOG: Dict[str, TeachingRule] = {
    "ATTENTION_DROP": TeachingRule(
        alert_type="ATTENTION_DROP",
        priority="warning",
        title="Visual Orientation Drop Detected",
        suggestion="Introduce a 30-second rapid check-in question or conduct a quick think-pair-share prompt.",
        rationale="Over 40% of observed participants exhibited downward gaze (notes/phones) or diverted head orientation over the past 12 seconds.",
        instructional_purpose="Re-align classroom attention and encourage active student participation."
    ),
    "MONOLOGUE_PACING": TeachingRule(
        alert_type="MONOLOGUE_PACING",
        priority="info",
        title="Extended Monologue Pacing",
        suggestion="Pause for 15 seconds to solicit questions, or ask for a simple thumbs-up/thumbs-down check.",
        rationale="Continuous monologue has exceeded 90 seconds without reciprocal student dialogue or pauses.",
        instructional_purpose="Improve knowledge retention by breaking passive listening cycles."
    ),
    "HIGH_INTERACTION": TeachingRule(
        alert_type="HIGH_INTERACTION",
        priority="info",
        title="High Discussion Energy",
        suggestion="Excellent peer interaction. Capture 1-2 core student ideas on the board and synthesize key takeaways.",
        rationale="Acoustic dynamics and active participant movement indicate high collaborative discussion.",
        instructional_purpose="Consolidate learning outcomes while engagement momentum is peak."
    ),
    "LOW_ACTIVITY": TeachingRule(
        alert_type="LOW_ACTIVITY",
        priority="urgent",
        title="Low Classroom Activity Detected",
        suggestion="Initiate a quick physical posture reset, transition to practical exercises, or invite a volunteer to share.",
        rationale="Consistently low physical movement and speech activity observed across the past 20 seconds.",
        instructional_purpose="Revitalize classroom energy and prevent cognitive fatigue."
    ),
    "SENSOR_QUALITY_ISSUE": TeachingRule(
        alert_type="SENSOR_QUALITY_ISSUE",
        priority="warning",
        title="Sensor Signal Degradation",
        suggestion="Check camera positioning or microphone connection. The system is operating on reduced multimodal coverage.",
        rationale="One or more sensory inputs (video stream or microphone) became unavailable or intermittent.",
        instructional_purpose="Ensure high-fidelity telemetry collection for instructional insights."
    ),
    "SESSION_MILESTONE": TeachingRule(
        alert_type="SESSION_MILESTONE",
        priority="info",
        title="Mid-Session Check-in",
        suggestion="Review key concepts covered so far before moving into the next module.",
        rationale="Half of the allocated lecture time has elapsed with stable sustained attendance.",
        instructional_purpose="Anchor intermediate learning milestones."
    )
}
