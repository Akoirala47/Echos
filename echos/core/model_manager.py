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
_FALLBACK_BYTES = 5 * 1024 ** 3  # used only if HF Hub metadata unavailable


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
            return try_to_load_from_cache(self.MODEL_ID, "config.json") is not None
        except Exception:
            return False

    def is_fully_cached(self) -> bool:
        """Return True only when the complete model snapshot is present locally."""
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
        """Query HF Hub for the actual total model size."""
        try:
            from huggingface_hub import model_info
            info = model_info(self.MODEL_ID)
            total = sum(
                s.size for s in (info.siblings or []) if s.size is not None
            )
            return total if total > 0 else _FALLBACK_BYTES
        except Exception:
            return _FALLBACK_BYTES

    def download(self, progress_callback: Callable[[int, int], None] | None = None) -> None:
        """Download model weights with smooth, non-negative progress reporting."""
        import threading as _threading
        from huggingface_hub import snapshot_download, constants as hf_constants

        expected_bytes = self._get_expected_bytes()
        logger.info("Expected model size: %.2f GB", expected_bytes / 1024 ** 3)

        cache_dir = Path(hf_constants.HF_HUB_CACHE)
        model_cache_dir = cache_dir / f"models--{self.MODEL_ID.replace('/', '--')}"

        stop_polling = _threading.Event()
        # Track the high-water mark so progress never goes backwards.
        _state = {"max_seen": 0}

        def _poll_size() -> None:
            while not stop_polling.is_set():
                try:
                    # Only count complete blobs — skip .incomplete temp files.
                    done = sum(
                        f.stat().st_size
                        for f in model_cache_dir.rglob("*")
                        if f.is_file() and not f.name.endswith(".incomplete")
                        and not f.name.endswith(".lock")
                    )
                except OSError:
                    done = 0
                # Clamp: never go backwards, never exceed expected total.
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
    # Load  (tries multiple strategies — Canary may need NeMo or custom class)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load model into memory. Tries multiple loading strategies in order."""
        with self._load_lock:
            if self._model is not None:
                return

            import torch
            dtype = torch.float16 if self._device == "mps" else torch.float32
            errors: list[str] = []

            # Strategy 1: AutoModel with trust_remote_code (handles custom architectures)
            try:
                from transformers import AutoModel, AutoProcessor
                logger.info("Trying AutoModel + AutoProcessor for %s", self.MODEL_ID)
                self._processor = AutoProcessor.from_pretrained(
                    self.MODEL_ID, trust_remote_code=True
                )
                self._model = (
                    AutoModel.from_pretrained(
                        self.MODEL_ID,
                        torch_dtype=dtype,
                        trust_remote_code=True,
                    )
                    .to(self._device)
                )
                self._model.eval()
                logger.info("Loaded via AutoModel on %s", self._device)
                return
            except Exception as exc:
                errors.append(f"AutoModel: {exc}")
                logger.warning("AutoModel failed: %s", exc)

            # Strategy 2: AutoModelForSpeechSeq2Seq (standard ASR path)
            try:
                from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
                logger.info("Trying AutoModelForSpeechSeq2Seq for %s", self.MODEL_ID)
                self._processor = AutoProcessor.from_pretrained(self.MODEL_ID)
                self._model = (
                    AutoModelForSpeechSeq2Seq.from_pretrained(
                        self.MODEL_ID,
                        torch_dtype=dtype,
                    )
                    .to(self._device)
                )
                self._model.eval()
                logger.info("Loaded via AutoModelForSpeechSeq2Seq on %s", self._device)
                return
            except Exception as exc:
                errors.append(f"AutoModelForSpeechSeq2Seq: {exc}")
                logger.warning("AutoModelForSpeechSeq2Seq failed: %s", exc)

            # Strategy 3: NeMo EncDecMultiTaskModel (NVIDIA Canary native format)
            try:
                logger.info("Trying NeMo EncDecMultiTaskModel for %s", self.MODEL_ID)
                from nemo.collections.asr.models import EncDecMultiTaskModel  # type: ignore
                self._model = EncDecMultiTaskModel.from_pretrained(self.MODEL_ID)
                self._processor = None  # NeMo handles processing internally
                logger.info("Loaded via NeMo EncDecMultiTaskModel")
                return
            except Exception as exc:
                errors.append(f"NeMo EncDecMultiTaskModel: {exc}")
                logger.warning("NeMo load failed: %s", exc)

            raise RuntimeError(
                f"Could not load {self.MODEL_ID} with any known strategy.\n\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a float32 mono audio chunk. Returns transcribed text."""
        if self._model is None:
            raise RuntimeError("Model not loaded — call load() first")

        import torch

        # NeMo path (no processor)
        if self._processor is None:
            return self._transcribe_nemo(audio_chunk, sample_rate)

        inputs = self._processor(
            audio_chunk,
            sampling_rate=sample_rate,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            output_ids = self._model.generate(**inputs)

        return self._processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

    def _transcribe_nemo(self, audio_chunk: np.ndarray, sample_rate: int) -> str:
        """Transcribe using a NeMo model (no HF processor)."""
        import tempfile, soundfile as sf
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio_chunk, sample_rate)
            result = self._model.transcribe([tmp.name])
        import os; os.unlink(tmp.name)
        return result[0] if result else ""


# ---------------------------------------------------------------------------
# ModelDownloadWorker — QThread wrapper around ModelManager.download()
# ---------------------------------------------------------------------------

class ModelDownloadWorker(QThread):
    """Downloads Canary-Qwen weights in a background thread."""

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
