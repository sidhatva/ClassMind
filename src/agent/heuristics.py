"""
Pedagogical Heuristics and Recommendation Rules for Classroom Intelligence.
Translates multi-sensor engagement telemetry into actionable teaching interventions.
"""

from typing import Dict, List, Optional


class TeachingRule:
    def __init__(self, alert_type: str, severity: str, title: str, suggestion: str, rationale: str):
        self.alert_type = alert_type
        self.severity = severity  # "info", "warning", "urgent"
        self.title = title
        self.suggestion = suggestion
        self.rationale = rationale


RULES_CATALOG = [
    TeachingRule(
        alert_type="ATTENTION_DROP",
        severity="warning",
        title="Attention Drop Detected",
        suggestion="Introduce a 30-second rapid check-in question or live interactive poll.",
        rationale="Over 40% of participants exhibited downward gaze (phone/desk) or diverted head orientation over the past 15 seconds."
    ),
    TeachingRule(
        alert_type="MONOLOGUE_PACING",
        severity="info",
        title="Extended Monologue Pacing",
        suggestion="Pause for 15 seconds to solicit student questions, or prompt a 'think-pair-share'.",
        rationale="Continuous instructor speech has exceeded 90 seconds without reciprocal student dialogue."
    ),
    TeachingRule(
        alert_type="HIGH_INTERACTION",
        severity="info",
        title="High Discussion Energy",
        suggestion="Excellent peer interaction. Capture key insights on board and summarize main takeaways before advancing.",
        rationale="Vocal energy and active postures are synchronized at optimal engagement levels."
    ),
    TeachingRule(
        alert_type="PROLONGED_SILENCE",
        severity="warning",
        title="Extended Classroom Silence",
        suggestion="Reframe the previous prompt or ask for a simple thumbs-up/down gesture to break the hesitation.",
        rationale="Vocal activity has been inactive for over 20 seconds following an instructional transition."
    ),
    TeachingRule(
        alert_type="PHYSICAL_INACTIVITY",
        severity="urgent",
        title="Lethargic Classroom State",
        suggestion="Initiate a quick physical posture reset or ask students to stand up for a 1-minute energizer.",
        rationale="Zero motion detected across multiple participants; posture signals drowsiness or low energy."
    )
]
