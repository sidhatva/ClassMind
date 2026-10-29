"""
ClassMind AI - Deterministic Simulation Engine Tests.
Validates fixed-seed reproducibility, avatar posture generation,
scheduled arrivals/departures, and pedagogical scenario transitions.
"""

import unittest
import numpy as np
from src.simulation.classroom_simulator import DeterministicClassroomSimulator


class TestClassroomSimulation(unittest.TestCase):
    def test_seed_reproducibility(self):
        """Two simulator instances with the identical seed produce identical output."""
        sim1 = DeterministicClassroomSimulator(seed=1234)
        sim2 = DeterministicClassroomSimulator(seed=1234)

        frame1, parts1, ids1 = sim1.generate_frame(t=15.0)
        frame2, parts2, ids2 = sim2.generate_frame(t=15.0)

        # Identical detected student IDs
        self.assertEqual(ids1, ids2)
        # Identical pixel frames
        self.assertTrue(np.array_equal(frame1, frame2))

    def test_scheduled_late_arrival(self):
        """Simulated student S104 arrives at t=40s and should not appear before then."""
        sim = DeterministicClassroomSimulator(seed=42)

        # At t=10s, S104 has not arrived yet
        _, _, ids_early = sim.generate_frame(t=10.0)
        self.assertNotIn("S104", ids_early)

        # At t=45s, S104 has arrived
        _, _, ids_late = sim.generate_frame(t=45.0)
        self.assertIn("S104", ids_late)

    def test_scenario_phase_audio_generation(self):
        """Audio chunk characteristics change dynamically based on simulated phase."""
        sim = DeterministicClassroomSimulator(seed=42)

        # Extended monologue phase (t=45s) has speech active
        audio_monologue = sim.generate_audio_chunk(t=45.0)
        self.assertTrue(audio_monologue["is_speech"])
        self.assertGreater(audio_monologue["audio_activity_score"], 0.70)

        # Attention drop / quiet phase (t=110s) has lower speech activity
        audio_quiet = sim.generate_audio_chunk(t=110.0)
        self.assertFalse(audio_quiet["is_speech"])
        self.assertLess(audio_quiet["audio_activity_score"], 0.35)


if __name__ == "__main__":
    unittest.main()
