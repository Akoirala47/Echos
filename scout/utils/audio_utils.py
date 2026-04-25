from __future__ import annotations

import re

import numpy as np


def compute_rms(chunk: np.ndarray) -> float:
    """Return normalised RMS energy in [0.0, 1.0].

    Input is expected to be float32 in the range [-1.0, 1.0].
    """
    if chunk.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
    # Clamp to [0, 1] — values above 1.0 indicate clipping but shouldn't crash.
    return min(max(rms, 0.0), 1.0)


def split_into_chunks(
    buffer: np.ndarray,
    chunk_samples: int,
    overlap_samples: int,
) -> list[np.ndarray]:
    """Split a 1-D audio buffer into overlapping chunks.

    Returns a list of arrays each of length chunk_samples (or shorter for the
    final chunk if the buffer doesn't divide evenly).  Overlap is taken from
    the tail of the previous chunk.
    """
    if buffer.size == 0 or chunk_samples <= 0:
        return []

    chunks: list[np.ndarray] = []
    step = max(chunk_samples - overlap_samples, 1)
    start = 0
    while start < len(buffer):
        end = start + chunk_samples
        chunks.append(buffer[start:end])
        start += step
    return chunks


def deduplicate_overlap(prev_text: str, new_text: str) -> str:
    """Remove tokens from the start of new_text that already appear at the end
    of prev_text, to prevent duplicated words at chunk boundaries.

    Uses a simple longest-suffix / prefix match on word tokens.
    """
    if not prev_text or not new_text:
        return new_text

    prev_words = prev_text.split()
    new_words = new_text.split()

    if not prev_words or not new_words:
        return new_text

    # Find the longest overlap: tail of prev_words == head of new_words.
    max_overlap = min(len(prev_words), len(new_words))
    overlap_len = 0
    for n in range(max_overlap, 0, -1):
        if prev_words[-n:] == new_words[:n]:
            overlap_len = n
            break

    deduplicated = new_words[overlap_len:]
    return " ".join(deduplicated)
