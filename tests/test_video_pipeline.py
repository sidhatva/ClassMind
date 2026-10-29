"""
ClassMind AI - Video Pipeline & Streaming Verification Tests.
Validates synthetic simulation, hardware camera handling, MJPEG streaming,
privacy blur processing, and source toggling.
"""

import unittest
import cv2
import numpy as np
import time

from config import config
from src.pipeline import ClassroomPipeline
from src.simulation.classroom_simulator import DeterministicClassroomSimulator
from src.vision.face_tracker import FaceTracker


class TestVideoPipeline(unittest.TestCase):
    def setUp(self):
        from src.database import create_session, get_session
        if not get_session("TEST-VIDEO-01"):
            create_session("TEST-VIDEO-01", "Test Video Session", "Section A", 6)
        self.pipeline = ClassroomPipeline(
            session_id="TEST-VIDEO-01",
            video_source=0,
            force_simulation=True
        )

    def tearDown(self):
        self.pipeline.release()

    def test_simulation_generates_valid_640x480_frames(self):
        """Verify simulation mode produces valid 640x480 RGB frames with participants."""
        frame, output = self.pipeline.process_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertEqual(frame.dtype, np.uint8)

        # Check that frame is not solid black (mean intensity > 10)
        self.assertGreater(frame.mean(), 15.0)

        # Check that participants are tracked in simulation
        participants = output.get("participants", [])
        self.assertGreater(len(participants), 0)
        self.assertTrue(output.get("use_simulation"))

    def test_jpeg_frame_encoding(self):
        """Verify get_jpeg_frame returns a valid JPEG streamable byte buffer."""
        jpeg_bytes = self.pipeline.get_jpeg_frame()
        self.assertIsInstance(jpeg_bytes, bytes)
        self.assertGreater(len(jpeg_bytes), 1000)

        # Verify JPEG magic bytes (SOI marker 0xFFD8)
        self.assertEqual(jpeg_bytes[:2], b"\xff\xd8")

        # Decode back to OpenCV image to verify image integrity
        np_arr = np.frombuffer(jpeg_bytes, np.uint8)
        decoded = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.shape, (480, 640, 3))

    def test_privacy_blur_changes_face_pixels(self):
        """Verify privacy blurring visibly transforms face crop pixels."""
        tracker = FaceTracker()
        test_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        # Create patterned face region
        test_frame[100:180, 100:180] = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
        orig_crop = test_frame[100:180, 100:180].copy()

        blurred_frame = tracker.apply_privacy_blur(test_frame.copy(), (100, 100, 80, 80))
        blurred_crop = blurred_frame[100:180, 100:180]

        # The pixel values in the face region must be altered by the Gaussian blur
        diff = np.abs(orig_crop.astype(float) - blurred_crop.astype(float)).mean()
        self.assertGreater(diff, 1.0)

    def test_source_toggling_without_restart(self):
        """Verify seamless toggle between simulation and hardware mode without crash."""
        self.assertTrue(self.pipeline.use_simulation)

        # Attempt to toggle to hardware mode
        self.pipeline.set_simulation_mode(False)
        # Whether physical webcam is present or not, pipeline should remain stable
        frame, output = self.pipeline.process_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))

        # Toggle back to simulation mode
        self.pipeline.set_simulation_mode(True)
        self.assertTrue(self.pipeline.use_simulation)
        frame2, output2 = self.pipeline.process_frame()
        self.assertIsNotNone(frame2)
        self.assertEqual(frame2.shape, (480, 640, 3))
        self.assertTrue(output2.get("use_simulation"))

    def test_pause_screen_rendering(self):
        """Verify that pausing renders a clear pause overlay rather than black frame."""
        self.pipeline.set_paused(True)
        frame, output = self.pipeline.process_frame()
        self.assertIsNotNone(frame)
        self.assertTrue(output.get("is_paused"))
        # Frame should have non-zero content (the PAUSED banner text)
        self.assertGreater(frame.mean(), 10.0)

        # Resume
        self.pipeline.set_paused(False)
        frame2, output2 = self.pipeline._step_pipeline()
        self.assertFalse(output2.get("is_paused"))


if __name__ == "__main__":
    unittest.main()
