from __future__ import annotations

import logging
import re

from PyQt6.QtCore import QThread, pyqtSignal

from echos.utils.markdown import (
    build_continuation_prompt,
    build_continuation_system_instruction,
    build_prompt,
    build_system_instruction,
)

logger = logging.getLogger(__name__)

# Approximate characters per token (conservative — keeps chunks under the limit)
_CHARS_PER_TOKEN = 4
CHUNK_TOKEN_LIMIT = 875  # stay safely under the ~1 000-token API cap
CHUNK_CHAR_LIMIT = CHUNK_TOKEN_LIMIT * _CHARS_PER_TOKEN  # 3 500 chars

_THINKING_RE = re.compile(
    r'<(?:thinking|thought)>.*?</(?:thinking|thought)>',
    re.DOTALL | re.IGNORECASE,
)
_THINK_OPEN_RE = re.compile(r'<(?:thinking|thought)>', re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r'</(?:thinking|thought)>', re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    cleaned = _THINKING_RE.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _split_transcript(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list[str]:
    """Split *text* into chunks of at most *limit* chars at natural boundaries."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        window = remaining[:limit]
        # Prefer paragraph boundary
        cut = window.rfind('\n\n')
        if cut < limit // 3:
            # Fall back to sentence boundary
            cut = max(window.rfind('. '), window.rfind('.\n'))
        if cut < limit // 3:
            # Hard cut
            cut = limit - 1
        chunks.append(remaining[:cut + 1].strip())
        remaining = remaining[cut + 1:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


class NotesWorker(QThread):
    """Sends the transcript to Gemma via Google AI API and streams back notes.

    Long transcripts are automatically split into <=3 500-char chunks and sent
    as sequential API calls so no single request exceeds the ~1 000-token cap.

    Signals
    -------
    chunk_ready : str
        Emitted for each streaming fragment (thinking blocks filtered out).
    done : str
        Emitted once with the complete generated notes (clean, no frontmatter).
    error : str
        Emitted if the API call fails.
    """

    chunk_ready = pyqtSignal(str)
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        transcript: str,
        course_name: str,
        lecture_num: int,
        date: str,
        api_key: str,
        model_id: str,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        custom_instruction: str = "",
        fingerprint_engine=None,
        existing_fingerprints: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._transcript = transcript
        self._course_name = course_name
        self._lecture_num = lecture_num
        self._date = date
        self._api_key = api_key
        self._model_id = model_id
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._custom_instruction = custom_instruction
        self._fingerprint_engine = fingerprint_engine
        self._existing_fingerprints: list[str] = existing_fingerprints or []
        self.fingerprint_str: str = ""

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _stream_one(self, genai, model, prompt: str) -> str:
        """Call the API for one prompt, stream results with thinking filtered out.

        Returns the clean (stripped) text produced by this call.
        """
        response = model.generate_content(
            prompt,
            stream=True,
            generation_config=genai.types.GenerationConfig(
                temperature=self._temperature,
                max_output_tokens=self._max_tokens,
            ),
        )

        full_raw = ""
        emitted_len = 0

        for raw_chunk in response:
            text = raw_chunk.text
            if not text:
                continue
            full_raw += text

            # Only emit when no unclosed <thinking> block is in flight
            open_count = len(_THINK_OPEN_RE.findall(full_raw))
            close_count = len(_THINK_CLOSE_RE.findall(full_raw))
            if open_count <= close_count:
                stripped = _strip_thinking(full_raw)
                if len(stripped) > emitted_len:
                    self.chunk_ready.emit(stripped[emitted_len:])
                    emitted_len = len(stripped)

        return _strip_thinking(full_raw)

    # ── QThread entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)

            chunks = _split_transcript(self._transcript)
            total = len(chunks)
            full_notes = ""

            for idx, chunk_text in enumerate(chunks, start=1):
                if idx == 1:
                    model = genai.GenerativeModel(
                        self._model_id,
                        system_instruction=build_system_instruction(self._custom_instruction),
                    )
                    prompt = build_prompt(
                        self._course_name,
                        self._lecture_num,
                        self._date,
                        chunk_text,
                    )
                else:
                    model = genai.GenerativeModel(
                        self._model_id,
                        system_instruction=build_continuation_system_instruction(),
                    )
                    notes_tail = full_notes[-400:] if len(full_notes) > 400 else full_notes
                    prompt = build_continuation_prompt(
                        session_name=self._course_name,
                        session_num=self._lecture_num,
                        date=self._date,
                        transcript_chunk=chunk_text,
                        chunk_idx=idx,
                        total_chunks=total,
                        notes_tail=notes_tail,
                    )
                    # Visual separator between chunks
                    if full_notes:
                        self.chunk_ready.emit("\n\n")

                added = self._stream_one(genai, model, prompt)
                full_notes = (full_notes + "\n\n" + added).strip() if full_notes else added

            clean = full_notes

            # ── Fingerprint generation (best-effort) ───────────────────────────
            if self._fingerprint_engine is not None:
                try:
                    fp = self._fingerprint_engine.generate(
                        clean,
                        self._existing_fingerprints,
                        self._api_key,
                        self._model_id,
                    )
                    self.fingerprint_str = fp.to_string()
                except Exception as fp_exc:
                    logger.warning("NotesWorker: fingerprint generation failed: %s", fp_exc)

            self.done.emit(clean)

        except Exception as exc:
            logger.exception("NotesWorker failed")
            self.error.emit(str(exc))
