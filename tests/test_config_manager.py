"""Unit tests for ConfigManager."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.config.config_manager import ConfigManager
from scout.config.defaults import DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def mgr(cfg_path: Path) -> ConfigManager:
    return ConfigManager(config_path=cfg_path)


# ---------------------------------------------------------------------------
# is_first_launch
# ---------------------------------------------------------------------------

def test_is_first_launch_true_when_no_file(mgr: ConfigManager) -> None:
    assert mgr.is_first_launch() is True


def test_is_first_launch_false_when_file_exists(mgr: ConfigManager, cfg_path: Path) -> None:
    cfg_path.write_text("{}", encoding="utf-8")
    assert mgr.is_first_launch() is False


# ---------------------------------------------------------------------------
# load — defaults
# ---------------------------------------------------------------------------

def test_load_returns_defaults_when_no_file(mgr: ConfigManager) -> None:
    result = mgr.load()
    assert result == DEFAULT_CONFIG


def test_load_returns_defaults_on_corrupt_json(mgr: ConfigManager, cfg_path: Path) -> None:
    cfg_path.write_text("not json {{{{", encoding="utf-8")
    result = mgr.load()
    assert result == DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# load — merge
# ---------------------------------------------------------------------------

def test_load_merges_partial_config_with_defaults(mgr: ConfigManager, cfg_path: Path) -> None:
    partial = {"vault_path": "/some/vault", "temperature": 0.9}
    cfg_path.write_text(json.dumps(partial), encoding="utf-8")
    result = mgr.load()
    # User values preserved
    assert result["vault_path"] == "/some/vault"
    assert result["temperature"] == 0.9
    # Missing keys filled from defaults
    assert result["gemma_model"] == DEFAULT_CONFIG["gemma_model"]
    assert result["max_tokens"] == DEFAULT_CONFIG["max_tokens"]


def test_load_does_not_mutate_defaults(mgr: ConfigManager, cfg_path: Path) -> None:
    cfg_path.write_text(json.dumps({"vault_path": "/x"}), encoding="utf-8")
    mgr.load()
    assert DEFAULT_CONFIG["vault_path"] == ""


# ---------------------------------------------------------------------------
# save / roundtrip
# ---------------------------------------------------------------------------

def test_save_creates_file(mgr: ConfigManager, cfg_path: Path) -> None:
    mgr.save({"version": "1.0", "vault_path": "/vault"})
    assert cfg_path.exists()


def test_save_load_roundtrip(mgr: ConfigManager) -> None:
    data = dict(DEFAULT_CONFIG)
    data["vault_path"] = "/my/vault"
    data["temperature"] = 0.7
    mgr.save(data)
    loaded = mgr.load()
    assert loaded["vault_path"] == "/my/vault"
    assert loaded["temperature"] == 0.7


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    deep_path = tmp_path / "a" / "b" / "c" / "config.json"
    mgr = ConfigManager(config_path=deep_path)
    mgr.save({"version": "1.0"})
    assert deep_path.exists()


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def test_atomic_write_uses_rename(mgr: ConfigManager, cfg_path: Path, tmp_path: Path) -> None:
    """save() should write via a temp file and then rename it atomically."""
    written_temps: list[str] = []
    original_replace = os.replace

    def capturing_replace(src: str, dst: str) -> None:
        written_temps.append(src)
        original_replace(src, dst)

    with patch("scout.config.config_manager.os.replace", side_effect=capturing_replace):
        mgr.save({"version": "1.0"})

    assert len(written_temps) == 1
    # The temp file should have been renamed away — only config.json remains.
    assert cfg_path.exists()
    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 1 and remaining[0] == cfg_path


def test_atomic_write_cleans_up_temp_on_failure(mgr: ConfigManager, tmp_path: Path) -> None:
    """If os.replace raises, the temp file must be cleaned up."""
    with patch("scout.config.config_manager.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            mgr.save({"version": "1.0"})

    # No leftover .tmp files
    temps = list(tmp_path.glob("*.tmp"))
    assert temps == []
