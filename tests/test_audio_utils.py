"""Unit tests for audio_utils."""

from __future__ import annotations

import numpy as np
import pytest

from scout.utils.audio_utils import compute_rms, deduplicate_overlap, split_into_chunks


# ---------------------------------------------------------------------------
# compute_rms
# ---------------------------------------------------------------------------

def test_rms_silence_returns_zero() -> None:
    audio = np.zeros(1000, dtype=np.float32)
    assert compute_rms(audio) == 0.0


def test_rms_full_scale_returns_one() -> None:
    audio = np.ones(1000, dtype=np.float32)
    assert compute_rms(audio) == pytest.approx(1.0, abs=1e-6)


def test_rms_half_scale() -> None:
    audio = np.full(1000, 0.5, dtype=np.float32)
    assert compute_rms(audio) == pytest.approx(0.5, abs=1e-4)


def test_rms_clamps_above_one() -> None:
    # Values > 1.0 (clipping) must be clamped to 1.0.
    audio = np.full(100, 2.0, dtype=np.float32)
    assert compute_rms(audio) == 1.0


def test_rms_empty_array_returns_zero() -> None:
    assert compute_rms(np.array([], dtype=np.float32)) == 0.0


def test_rms_negative_values() -> None:
    # RMS is always non-negative regardless of sign.
    audio = np.full(100, -0.5, dtype=np.float32)
    assert compute_rms(audio) == pytest.approx(0.5, abs=1e-4)


def test_rms_mixed_signal() -> None:
    # A sine wave has RMS = amplitude / sqrt(2).
    t = np.linspace(0, 2 * np.pi, 16000, dtype=np.float32)
    audio = 0.8 * np.sin(t)
    expected = 0.8 / np.sqrt(2)
    assert compute_rms(audio) == pytest.approx(expected, abs=1e-3)


# ---------------------------------------------------------------------------
# split_into_chunks
# ---------------------------------------------------------------------------

def test_split_basic_no_overlap() -> None:
    audio = np.arange(20, dtype=np.float32)
    chunks = split_into_chunks(audio, chunk_samples=5, overlap_samples=0)
    assert len(chunks) == 4
    np.testing.assert_array_equal(chunks[0], [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(chunks[3], [15, 16, 17, 18, 19])


def test_split_with_overlap() -> None:
    audio = np.arange(10, dtype=np.float32)
    # chunk=5, overlap=2 → step=3 → starts at 0, 3, 6, 9 (4 chunks)
    chunks = split_into_chunks(audio, chunk_samples=5, overlap_samples=2)
    assert len(chunks) == 4
    np.testing.assert_array_equal(chunks[0], [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(chunks[1], [3, 4, 5, 6, 7])
    # Remaining chunks are shorter than chunk_samples.
    assert len(chunks[2]) <= 5
    assert len(chunks[3]) <= 5


def test_split_empty_buffer_returns_empty() -> None:
    chunks = split_into_chunks(np.array([], dtype=np.float32), 5, 1)
    assert chunks == []


def test_split_chunk_larger_than_buffer() -> None:
    audio = np.arange(3, dtype=np.float32)
    chunks = split_into_chunks(audio, chunk_samples=10, overlap_samples=0)
    assert len(chunks) == 1
    np.testing.assert_array_equal(chunks[0], audio)


def test_split_overlap_creates_shared_samples() -> None:
    audio = np.arange(12, dtype=np.float32)
    chunks = split_into_chunks(audio, chunk_samples=6, overlap_samples=2)
    # Chunks should share 2 samples at the boundary.
    assert chunks[0][-2:].tolist() == chunks[1][:2].tolist()


# ---------------------------------------------------------------------------
# deduplicate_overlap
# ---------------------------------------------------------------------------

def test_dedup_no_overlap_returns_new_text() -> None:
    result = deduplicate_overlap("hello world", "foo bar")
    assert result == "foo bar"


def test_dedup_removes_overlapping_words() -> None:
    result = deduplicate_overlap("the quick brown fox", "brown fox jumps over")
    assert result == "jumps over"


def test_dedup_full_overlap_returns_empty() -> None:
    result = deduplicate_overlap("hello world", "hello world")
    assert result == ""


def test_dedup_single_word_overlap() -> None:
    result = deduplicate_overlap("end of sentence", "sentence continues here")
    assert result == "continues here"


def test_dedup_empty_prev_returns_new() -> None:
    assert deduplicate_overlap("", "some text") == "some text"


def test_dedup_empty_new_returns_empty() -> None:
    assert deduplicate_overlap("some text", "") == ""


def test_dedup_both_empty() -> None:
    assert deduplicate_overlap("", "") == ""


def test_dedup_no_common_words() -> None:
    result = deduplicate_overlap("alpha beta gamma", "delta epsilon zeta")
    assert result == "delta epsilon zeta"
