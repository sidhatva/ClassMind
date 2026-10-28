"""
Classroom Interaction Dynamics Tracker.
Monitors acoustic dynamics, speaker transitions, and detects extended monologues or dead silence.
"""

from typing import Dict


class InteractionTracker:
    def __init__(self):
        self.speech_intervals = []
        self.total_speech_sec = 0.0
        self.total_silence_sec = 0.0
        self.consecutive_speech_sec = 0.0
        self.consecutive_silence_sec = 0.0

    def update(self, is_speech: bool, dt: float) -> Dict[str, any]:
        """
        Updates interaction statistics over time step dt.
        """
        if is_speech:
            self.total_speech_sec += dt
            self.consecutive_speech_sec += dt
            self.consecutive_silence_sec = 0.0
        else:
            self.total_silence_sec += dt
            self.consecutive_silence_sec += dt
            self.consecutive_speech_sec = 0.0

        total_time = max(0.1, self.total_speech_sec + self.total_silence_sec)
        talk_ratio = self.total_speech_sec / total_time

        # Detect interaction mode
        if self.consecutive_silence_sec > 15.0:
            mode = "Extended Silence / Inactivity"
        elif self.consecutive_speech_sec > 90.0:
            mode = "Continuous Monologue"
        elif talk_ratio > 0.4 and talk_ratio < 0.8:
            mode = "Dynamic Discussion / Interactive Q&A"
        else:
            mode = "Standard Lecture"

        return {
            "mode": mode,
            "talk_ratio": round(talk_ratio, 2),
            "consecutive_speech_sec": round(self.consecutive_speech_sec, 1),
            "consecutive_silence_sec": round(self.consecutive_silence_sec, 1)
        }
