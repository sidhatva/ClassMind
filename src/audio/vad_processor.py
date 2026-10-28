"""
Audio Signal Processing & Voice Activity Detection (VAD).
Analyzes classroom acoustic levels, speech vs. silence ratios,
and interaction dynamics. Includes live microphone capture with synthetic fallback.
"""

import math
import time
import numpy as np
from typing import Dict, Optional
from config import config


class AudioVADProcessor:
    def __init__(self, sample_rate: int = 16000, chunk_duration_sec: float = 0.5):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration_sec)
        self.energy_threshold = config.engagement.audio_energy_threshold
        
        # Audio state tracking
        self.is_speech_active = False
        self.current_energy = 0.0
        self.speech_chunks_count = 0
        self.total_chunks_count = 0
        self.last_speech_time = time.time()
        self.silence_duration_sec = 0.0
        
        # Live microphone initialization (optional)
        self.live_stream = None
        self._init_live_mic()

    def _init_live_mic(self):
        """Attempts to initialize PyAudio stream if available and permissions allow."""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            self.live_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
        except Exception:
            # Graceful fallback to synthetic classroom simulation
            self.live_stream = None

    def read_audio_chunk(self, current_time: float) -> np.ndarray:
        """Reads a chunk from microphone or generates realistic classroom acoustic waves."""
        if self.live_stream is not None:
            try:
                data = self.live_stream.read(self.chunk_size, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                return audio_np
            except Exception:
                pass

        # Realistic synthetic acoustic modeling:
        # Pacing: periodic lecturer monologue (3-8s bursts) + occasional pauses + student question bursts
        t = current_time
        # Multi-frequency voice harmonics + subtle background white noise
        base_voice_pattern = (math.sin(t * 1.5) > 0.1) or (math.sin(t * 0.4) > 0.4)
        noise = np.random.normal(0, 0.005, self.chunk_size).astype(np.float32)
        
        if base_voice_pattern:
            carrier = np.sin(2 * np.pi * 220 * np.linspace(0, 0.5, self.chunk_size)) * 0.08
            carrier += np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, self.chunk_size)) * 0.04
            return (carrier + noise).astype(np.float32)
        else:
            return noise

    def process_chunk(self, current_time: float) -> Dict[str, float]:
        """
        Analyzes the latest audio chunk for VAD, energy, and speech ratio.
        """
        audio_chunk = self.read_audio_chunk(current_time)
        
        # Calculate Root Mean Square (RMS) energy
        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        self.current_energy = rms
        self.total_chunks_count += 1

        is_speech = rms > self.energy_threshold
        if is_speech:
            self.speech_chunks_count += 1
            self.last_speech_time = current_time
            self.silence_duration_sec = 0.0
            self.is_speech_active = True
        else:
            self.silence_duration_sec = current_time - self.last_speech_time
            self.is_speech_active = False

        # Ratio of vocal engagement in the session (windowed)
        speech_ratio = self.speech_chunks_count / max(1, self.total_chunks_count)
        
        # Audio activity score: high speech energy scores 0.7 - 0.95; dead silence drops to 0.1
        if is_speech:
            audio_activity_score = min(1.0, 0.6 + (rms / 0.15) * 0.4)
        else:
            # Extended silence decreases engagement score
            audio_activity_score = max(0.15, 0.5 - min(0.35, self.silence_duration_sec / 30.0))

        return {
            "is_speech": is_speech,
            "rms_energy": round(rms, 4),
            "audio_activity_score": round(audio_activity_score, 2),
            "silence_seconds": round(self.silence_duration_sec, 1),
            "speech_ratio": round(speech_ratio, 2)
        }
