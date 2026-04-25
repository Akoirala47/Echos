from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from scout.utils.audio_utils import compute_rms, deduplicate_overlap, split_into_chunks

if TYPE_CHECKING:
    from scout.core.model_manager import ModelManager

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_CHANNELS = 1
_DTYPE = "float32"
# How often the waveform level signal fires (seconds).
_LEVEL_INTERVAL = 1.0 / 30


class AudioWorker(QThread):
    """Captures microphone audio and transcribes chunks with Canary-Qwen.

    Signals
    -------
    transcript_chunk : str
        Emitted each time a chunk is transcribed (~every chunk_seconds).
    audio_level : float
        Emitted at ~30 fps with normalised RMS in [0.0, 1.0].
    error : str
        Emitted on non-fatal transcription errors; recording continues.
    """

    transcript_chunk = pyqtSignal(str)
    audio_level = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(
        self,
        model_manager: "ModelManager",
        chunk_seconds: float = 6.0,
        overlap_seconds: float = 0.5,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._model_manager = model_manager
        self._chunk_seconds = chunk_seconds
        self._overlap_seconds = overlap_seconds

        self._chunk_samples = int(chunk_seconds * _SAMPLE_RATE)
        self._overlap_samples = int(overlap_seconds * _SAMPLE_RATE)

        # Threading primitives — all state mutations happen on this thread.
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially

        # Rolling buffer of float32 samples.
        self._buffer: np.ndarray = np.empty(0, dtype=np.float32)
        self._last_transcript: str = ""

        # Small deque for computing RMS across the most recent audio callback.
        self._level_deque: deque[float] = deque(maxlen=10)
        self._level_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public control slots (safe to call from main thread)
    # ------------------------------------------------------------------

    def pause(self) -> None:
        self._pause_event.clear()
        logger.debug("AudioWorker paused")

    def resume(self) -> None:
        self._pause_event.set()
        logger.debug("AudioWorker resumed")

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()  # unblock any wait() so the thread can exit
        logger.debug("AudioWorker stop requested")

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            self.error.emit(f"sounddevice not available: {exc}")
            return

        self._stop_event.clear()
        self._buffer = np.empty(0, dtype=np.float32)
        self._last_transcript = ""

        def _audio_callback(
            indata: np.ndarray,
            frames: int,
            time_info,
            status,
        ) -> None:
            if status:
                logger.warning("sounddevice status: %s", status)
            chunk = indata[:, 0].copy()  # mono
            with self._level_lock:
                self._level_deque.append(compute_rms(chunk))
            # Only accumulate samples when not paused.
            if self._pause_event.is_set():
                self._buffer = np.concatenate([self._buffer, chunk])

        try:
            stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                callback=_audio_callback,
                blocksize=int(_SAMPLE_RATE * 0.1),  # 100 ms blocks
            )
        except Exception as exc:
            self.error.emit(f"Could not open microphone: {exc}")
            return

        last_level_time = time.monotonic()
        last_chunk_boundary = 0  # index into self._buffer where last chunk ended

        with stream:
            while not self._stop_event.is_set():
                now = time.monotonic()

                # Emit audio level at ~30 fps.
                if now - last_level_time >= _LEVEL_INTERVAL:
                    with self._level_lock:
                        level = (
                            float(np.mean(list(self._level_deque)))
                            if self._level_deque
                            else 0.0
                        )
                    self.audio_level.emit(level)
                    last_level_time = now

                # Check if we have a full chunk ready to transcribe.
                available = len(self._buffer) - last_chunk_boundary
                if available >= self._chunk_samples:
                    chunk_end = last_chunk_boundary + self._chunk_samples
                    audio_chunk = self._buffer[last_chunk_boundary:chunk_end]

                    try:
                        text = self._model_manager.transcribe(audio_chunk, _SAMPLE_RATE)
                        if text:
                            deduped = deduplicate_overlap(self._last_transcript, text)
                            if deduped.strip():
                                self._last_transcript = (
                                    self._last_transcript + " " + deduped
                                ).strip()
                                self.transcript_chunk.emit(deduped)
                    except Exception as exc:
                        logger.exception("Transcription error on chunk")
                        self.error.emit(str(exc))

                    # Advance boundary by step (chunk minus overlap).
                    step = self._chunk_samples - self._overlap_samples
                    last_chunk_boundary += max(step, 1)

                    # Trim buffer to avoid unbounded growth; keep overlap tail.
                    keep_from = max(last_chunk_boundary - self._overlap_samples, 0)
                    self._buffer = self._buffer[keep_from:]
                    last_chunk_boundary -= keep_from

                # Yield ~10 ms so we don't spin at 100% CPU.
                self._stop_event.wait(timeout=0.01)

        logger.info("AudioWorker finished")
