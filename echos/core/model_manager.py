from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_MODEL_ID = "nvidia/canary-qwen-2.5b"
# Approximate total download size used for progress estimation.
_EXPECTED_BYTES = 5 * 1024 ** 3  # 5 GB


class ModelManager:
    """Owns the Canary-Qwen ASR model lifecycle: cache check, download, load, infer."""

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
        """Override device selection ('auto', 'mps', 'cpu')."""
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
        """Return True if at least one model file exists locally (may be incomplete)."""
        try:
            from huggingface_hub import try_to_load_from_cache
            result = try_to_load_from_cache(self.MODEL_ID, "config.json")
            return result is not None
        except Exception:
            return False

    def is_fully_cached(self) -> bool:
        """Return True only when the complete model snapshot is present locally.

        Uses snapshot_download with local_files_only=True which raises if any
        file is missing, making it safe to call load() afterwards.
        """
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(self.MODEL_ID, local_files_only=True)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self, progress_callback: Callable[[int, int], None] | None = None) -> None:
        """Download model weights. Blocks until complete.

        progress_callback receives (bytes_done, bytes_total) periodically.
        Uses cache-dir size polling because HuggingFace Hub doesn't expose
        per-file progress natively at the snapshot level.
        """
        import threading as _threading
        from huggingface_hub import snapshot_download, constants as hf_constants

        cache_dir = Path(hf_constants.HF_HUB_CACHE)
        model_cache_dir = cache_dir / f"models--{self.MODEL_ID.replace('/', '--')}"

        stop_polling = _threading.Event()

        def _poll_size() -> None:
            while not stop_polling.is_set():
                try:
                    done = sum(
                        f.stat().st_size
                        for f in model_cache_dir.rglob("*")
                        if f.is_file()
                    )
                except OSError:
                    done = 0
                if progress_callback:
                    progress_callback(done, _EXPECTED_BYTES)
                stop_polling.wait(timeout=1.0)

        poller = _threading.Thread(target=_poll_size, daemon=True)
        poller.start()
        try:
            snapshot_download(self.MODEL_ID, local_files_only=False)
        finally:
            stop_polling.set()
            poller.join()
        if progress_callback:
            progress_callback(_EXPECTED_BYTES, _EXPECTED_BYTES)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load model into memory. Safe to call from a background thread."""
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            logger.info("Loading Canary-Qwen processor from %s", self.MODEL_ID)
            self._processor = AutoProcessor.from_pretrained(self.MODEL_ID)

            dtype = torch.float16 if self._device == "mps" else torch.float32
            logger.info("Loading model on device=%s dtype=%s", self._device, dtype)
            self._model = (
                AutoModelForSpeechSeq2Seq.from_pretrained(
                    self.MODEL_ID,
                    torch_dtype=dtype,
                )
                .to(self._device)
            )
            self._model.eval()
            logger.info("Model loaded successfully")

    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a float32 mono audio chunk. Returns transcribed text.

        Raises RuntimeError if the model is not yet loaded.
        """
        if self._model is None or self._processor is None:
            raise RuntimeError("Model not loaded — call load() first")

        import torch

        inputs = self._processor(
            audio_chunk,
            sampling_rate=sample_rate,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            output_ids = self._model.generate(**inputs)

        text: str = self._processor.batch_decode(
            output_ids, skip_special_tokens=True
        )[0]
        return text.strip()


# ---------------------------------------------------------------------------
# ModelDownloadWorker — QThread wrapper around ModelManager.download()
# ---------------------------------------------------------------------------

class ModelDownloadWorker(QThread):
    """Downloads Canary-Qwen weights in a background thread.

    Signals
    -------
    progress : (int, int)
        (bytes_done, bytes_total) — emitted approximately every second.
    done
        Emitted when the download completes successfully.
    error : str
        Emitted if the download fails.
    """

    progress = pyqtSignal(int, int)
    done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, model_manager: ModelManager, parent=None) -> None:
        super().__init__(parent)
        self._model_manager = model_manager
        self._last_bytes: int = 0
        self._last_time: float = 0.0
        self._speed_bps: float = 0.0

    def run(self) -> None:
        def _cb(bytes_done: int, bytes_total: int) -> None:
            now = time.monotonic()
            if self._last_time > 0:
                elapsed = now - self._last_time
                if elapsed > 0:
                    self._speed_bps = (bytes_done - self._last_bytes) / elapsed
            self._last_bytes = bytes_done
            self._last_time = now
            self.progress.emit(bytes_done, bytes_total)

        try:
            self._model_manager.download(progress_callback=_cb)
            self.done.emit()
        except Exception as exc:
            logger.exception("Model download failed")
            self.error.emit(str(exc))
