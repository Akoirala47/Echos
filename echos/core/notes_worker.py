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

_CHARS_PER_TOKEN = 4
CHUNK_TOKEN_LIMIT = 875
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
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = window.rfind('\n\n')
        if cut < limit // 3:
            cut = max(window.rfind('. '), window.rfind('.\n'))
        if cut < limit // 3:
            cut = limit - 1
        chunks.append(remaining[:cut + 1].strip())
        remaining = remaining[cut + 1:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _supports_thinking_budget(model_id: str) -> bool:
    """Only Gemini 2.x models support thinking_budget; Gemma and older do not."""
    m = model_id.lower().removeprefix("models/")
    return m.startswith("gemini-2.")


class NotesWorker(QThread):
    """Sends a transcript segment to the API and streams back notes.

    Uses google-genai SDK (>=1.0).  thinking_budget=0 is only sent for models
    that support it (Gemini 2.x).  The system instruction and _strip_thinking
    serve as fallback for other models.

    Signals
    -------
    chunk_ready : str   Clean streaming fragment.
    done        : str   Complete notes for this run.
    error       : str   Error message on failure.
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
        is_continuation: bool = False,
        existing_notes_tail: str = "",
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
        self._is_continuation = is_continuation
        self._existing_notes_tail = existing_notes_tail
        self._fingerprint_engine = fingerprint_engine
        self._existing_fingerprints: list[str] = existing_fingerprints or []
        self.fingerprint_str: str = ""

    def _stream_one(self, client, system_instruction: str, prompt: str) -> str:
        from google.genai import types

        cfg_kw: dict = dict(
            system_instruction=system_instruction,
            temperature=self._temperature,
            max_output_tokens=self._max_tokens,
        )
        if _supports_thinking_budget(self._model_id):
            cfg_kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

        full_raw = ""
        emitted_len = 0

        for chunk in client.models.generate_content_stream(
            model=self._model_id,
            contents=prompt,
            config=types.GenerateContentConfig(**cfg_kw),
        ):
            text = chunk.text or ""
            if not text:
                continue
            full_raw += text

            open_count = len(_THINK_OPEN_RE.findall(full_raw))
            close_count = len(_THINK_CLOSE_RE.findall(full_raw))
            if open_count <= close_count:
                stripped = _strip_thinking(full_raw)
                if len(stripped) > emitted_len:
                    self.chunk_ready.emit(stripped[emitted_len:])
                    emitted_len = len(stripped)

        return _strip_thinking(full_raw)

    def run(self) -> None:
        try:
            from google import genai

            client = genai.Client(api_key=self._api_key)
            chunks = _split_transcript(self._transcript)
            total = len(chunks)
            full_notes = ""

            for idx, chunk_text in enumerate(chunks, start=1):
                is_first = (idx == 1)

                if is_first and not self._is_continuation:
                    system_instr = build_system_instruction(self._custom_instruction)
                    prompt = build_prompt(
                        self._course_name, self._lecture_num,
                        self._date, chunk_text,
                    )
                else:
                    system_instr = build_continuation_system_instruction()
                    tail = (
                        self._existing_notes_tail if is_first
                        else (full_notes[-400:] if len(full_notes) > 400 else full_notes)
                    )
                    prompt = build_continuation_prompt(
                        session_name=self._course_name,
                        session_num=self._lecture_num,
                        date=self._date,
                        transcript_chunk=chunk_text,
                        chunk_idx=idx,
                        total_chunks=total,
                        notes_tail=tail,
                    )
                    if full_notes:
                        self.chunk_ready.emit("\n\n")

                added = self._stream_one(client, system_instr, prompt)
                full_notes = (full_notes + "\n\n" + added).strip() if full_notes else added

            if self._fingerprint_engine is not None:
                try:
                    fp = self._fingerprint_engine.generate(
                        full_notes,
                        self._existing_fingerprints,
                        self._api_key,
                        self._model_id,
                    )
                    self.fingerprint_str = fp.to_string()
                except Exception as fp_exc:
                    logger.warning("NotesWorker: fingerprint failed: %s", fp_exc)

            self.done.emit(full_notes)

        except Exception as exc:
            logger.exception("NotesWorker failed")
            self.error.emit(str(exc))
