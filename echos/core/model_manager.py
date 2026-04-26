from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_MODEL_ID = "openai/whisper-large-v3"
_FALLBACK_BYTES = 3 * 1024 ** 3  # ~3 GB actual size


class ModelManager:
    """Owns the Whisper large-v3 ASR model lifecycle: cache, download, load, infer."""

    MODEL_ID = _MODEL_ID

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._device: str = self._detect_device()
        self._load_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Device
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    @property
    def device(self) -> str:
        return self._device

    def set_device(self, device: str) -> None:
        if device == "auto":
            self._device = self._detect_device()
        elif device in ("mps", "cpu"):
            self._device = device
        else:
            raise ValueError(f"Unknown device: {device!r}")

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def is_cached(self) -> bool:
        """Return True if at least one model file exists locally."""
        try:
            from huggingface_hub import try_to_load_from_cache
            return try_to_load_from_cache(self.MODEL_ID, "config.json") is not None
        except Exception:
            return False

    def is_fully_cached(self) -> bool:
        """Return True only when the complete snapshot is present locally."""
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(self.MODEL_ID, local_files_only=True)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _get_expected_bytes(self) -> int:
        try:
            from huggingface_hub import model_info
            info = model_info(self.MODEL_ID)
            total = 0
            for s in (info.siblings or []):
                size = getattr(s, "size", None)
                if isinstance(size, int) and size > 0:
                    total += size
            # Guard against API quirks: clamp to fallback if suspiciously small.
            if total < _FALLBACK_BYTES // 2:
                return _FALLBACK_BYTES
            return total
        except Exception:
            return _FALLBACK_BYTES

    def download(self, progress_callback: Callable[[int, int], None] | None = None) -> None:
        """Download Whisper large-v3 weights with smooth non-negative progress."""
        import threading as _threading
        from huggingface_hub import snapshot_download, constants as hf_constants

        expected_bytes = self._get_expected_bytes()
        # Final safety net — never let a non-positive value reach the UI.
        if expected_bytes <= 0:
            expected_bytes = _FALLBACK_BYTES
        logger.info("Expected model size: %.2f GB", expected_bytes / 1024 ** 3)

        cache_dir = Path(hf_constants.HF_HUB_CACHE)
        model_cache_dir = cache_dir / f"models--{self.MODEL_ID.replace('/', '--')}"

        stop_polling = _threading.Event()
        _state = {"max_seen": 0}

        def _poll_size() -> None:
            while not stop_polling.is_set():
                try:
                    done = sum(
                        f.stat().st_size
                        for f in model_cache_dir.rglob("*")
                        if f.is_file()
                        and not f.name.endswith(".incomplete")
                        and not f.name.endswith(".lock")
                    )
                except OSError:
                    done = 0
                done = max(_state["max_seen"], done)
                done = min(done, expected_bytes)
                _state["max_seen"] = done
                if progress_callback:
                    progress_callback(done, expected_bytes)
                stop_polling.wait(timeout=1.0)

        poller = _threading.Thread(target=_poll_size, daemon=True)
        poller.start()
        try:
            snapshot_download(self.MODEL_ID, local_files_only=False)
        finally:
            stop_polling.set()
            poller.join()
        if progress_callback:
            progress_callback(expected_bytes, expected_bytes)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load Whisper large-v3 into memory on the appropriate device."""
        with self._load_lock:
            if self._model is not None:
                return

            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            logger.info("Loading Whisper processor from %s", self.MODEL_ID)
            self._processor = AutoProcessor.from_pretrained(self.MODEL_ID)

            dtype = torch.float16 if self._device == "mps" else torch.float32
            logger.info("Loading model on device=%s dtype=%s", self._device, dtype)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.MODEL_ID,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            ).to(self._device)
            self._model.eval()
            logger.info("Whisper large-v3 loaded on %s", self._device)

    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a float32 mono audio chunk. Returns transcribed text."""
        if self._model is None or self._processor is None:
            raise RuntimeError("Model not loaded — call load() first")

        import torch

        # Whisper processor pads/truncates to 30s automatically.
        inputs = self._processor(
            audio_chunk,
            sampling_rate=sample_rate,
            return_tensors="pt",
        ).to(self._device)

        # Match input dtype to model dtype (float16 on MPS, float32 on CPU).
        model_dtype = torch.float16 if self._device == "mps" else torch.float32
        inputs["input_features"] = inputs["input_features"].to(model_dtype)

        with torch.no_grad():
            generated_ids = self._model.generate(
                inputs["input_features"],
                language="en",
                task="transcribe",
            )

        return self._processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()


# ---------------------------------------------------------------------------
# ModelDownloadWorker
# ---------------------------------------------------------------------------

class ModelDownloadWorker(QThread):
    """Downloads Whisper large-v3 weights in a background thread."""

    progress = pyqtSignal(int, int)  # (bytes_done, bytes_total)
    done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, model_manager: ModelManager, parent=None) -> None:
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self) -> None:
        def _cb(bytes_done: int, bytes_total: int) -> None:
            self.progress.emit(bytes_done, bytes_total)

        try:
            self._model_manager.download(progress_callback=_cb)
            self.done.emit()
        except Exception as exc:
            logger.exception("Model download failed")
            self.error.emit(str(exc))
