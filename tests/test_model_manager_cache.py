"""Unit tests for ModelManager.is_cached() and device detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scout.core.model_manager import ModelManager


# ---------------------------------------------------------------------------
# is_cached
# ---------------------------------------------------------------------------

def test_is_cached_returns_true_when_config_found() -> None:
    mgr = ModelManager()
    with patch("huggingface_hub.try_to_load_from_cache", return_value="/some/path"):
        assert mgr.is_cached() is True


def test_is_cached_returns_false_when_not_cached() -> None:
    mgr = ModelManager()
    with patch("huggingface_hub.try_to_load_from_cache", return_value=None):
        assert mgr.is_cached() is False


def test_is_cached_returns_false_on_import_error() -> None:
    mgr = ModelManager()
    with patch("huggingface_hub.try_to_load_from_cache", side_effect=ImportError):
        assert mgr.is_cached() is False


def test_is_cached_returns_false_on_any_exception() -> None:
    mgr = ModelManager()
    with patch("huggingface_hub.try_to_load_from_cache", side_effect=RuntimeError("oops")):
        assert mgr.is_cached() is False


# ---------------------------------------------------------------------------
# is_loaded
# ---------------------------------------------------------------------------

def test_is_loaded_false_before_load() -> None:
    mgr = ModelManager()
    assert mgr.is_loaded() is False


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def test_device_is_mps_or_cpu() -> None:
    mgr = ModelManager()
    assert mgr.device in ("mps", "cpu")


def test_set_device_cpu() -> None:
    mgr = ModelManager()
    mgr.set_device("cpu")
    assert mgr.device == "cpu"


def test_set_device_auto_resolves() -> None:
    mgr = ModelManager()
    mgr.set_device("auto")
    assert mgr.device in ("mps", "cpu")


def test_set_device_invalid_raises() -> None:
    mgr = ModelManager()
    with pytest.raises(ValueError):
        mgr.set_device("cuda")


# ---------------------------------------------------------------------------
# transcribe raises when model not loaded
# ---------------------------------------------------------------------------

def test_transcribe_raises_if_not_loaded() -> None:
    import numpy as np
    mgr = ModelManager()
    with pytest.raises(RuntimeError, match="not loaded"):
        mgr.transcribe(np.zeros(16000, dtype=np.float32))
