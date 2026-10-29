"""
ClassMind AI - Audio Signal Processing & Voice Activity Detection (VAD).
Analyzes classroom acoustic levels, aggregate speech vs. silence ratios,
and interaction dynamics. Operates locally with device health monitoring.
"""

import math
import time
import numpy as np
from typing import Dict, Optional, Tuple, List, Any
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
        
        # Live microphone state
        self.live_stream = None
        self.pyaudio_instance = None
        self.mic_available = False
        self.device_name = "None (Simulated / Unavailable)"
        self._init_live_mic()

    def _init_live_mic(self):
        """Attempts to initialize PyAudio stream if available and permissions allow."""
        try:
            import pyaudio
            self.pyaudio_instance = pyaudio.PyAudio()
            # Check default input device
            default_info = self.pyaudio_instance.get_default_input_device_info()
            self.device_name = default_info.get("name", "Default Microphone")
            
            self.live_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            self.mic_available = True
            print(f"[Audio] Connected to physical microphone: {self.device_name}")
        except Exception as e:
            self.mic_available = False
            self.live_stream = None
            self.device_name = "Audio Inactive (Fallback)"

    def read_audio_chunk(self) -> Tuple[np.ndarray, bool]:
        """Reads a chunk from microphone if available, otherwise returns zero/synthetic noise."""
        if self.live_stream is not None and self.mic_available:
            try:
                data = self.live_stream.read(self.chunk_size, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                return audio_np, True
            except Exception:
                self.mic_available = False

        # Fallback quiet background room tone
        noise = np.random.normal(0, 0.003, self.chunk_size).astype(np.float32)
        return noise, self.mic_available

    def process_chunk(self, current_time: float, synthetic_chunk: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyzes the latest audio chunk for VAD, energy, and speech ratio.
        If a synthetic_chunk is provided (e.g. in simulation mode), uses it directly.
        """
        if synthetic_chunk is not None:
            self.is_speech_active = synthetic_chunk.get("is_speech", False)
            self.current_energy = synthetic_chunk.get("rms_energy", 0.0)
            if self.is_speech_active:
                self.speech_chunks_count += 1
                self.silence_duration_sec = 0.0
            else:
                self.silence_duration_sec += 0.5
            self.total_chunks_count += 1
            return synthetic_chunk

        audio_chunk, is_live = self.read_audio_chunk()
        
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

        speech_ratio = self.speech_chunks_count / max(1, self.total_chunks_count)
        
        # Audio activity score: high speech energy scores 0.7 - 0.95; dead silence drops to 0.15
        if is_speech:
            audio_activity_score = min(1.0, 0.6 + (rms / 0.15) * 0.4)
        else:
            audio_activity_score = max(0.15, 0.5 - min(0.35, self.silence_duration_sec / 30.0))

        return {
            "is_speech": is_speech,
            "rms_energy": round(rms, 4),
            "audio_activity_score": round(audio_activity_score, 2),
            "silence_seconds": round(self.silence_duration_sec, 1),
            "speech_ratio": round(speech_ratio, 2),
            "sensor_available": is_live,
            "device_name": self.device_name
        }

    def close(self):
        """Releases audio stream cleanly on shutdown."""
        if self.live_stream is not None:
            try:
                self.live_stream.stop_stream()
                self.live_stream.close()
            except Exception:
                pass
        if self.pyaudio_instance is not None:
            try:
                self.pyaudio_instance.terminate()
            except Exception:
                pass
