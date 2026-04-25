from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from scout.utils.markdown import build_prompt

logger = logging.getLogger(__name__)


class NotesWorker(QThread):
    """Sends the transcript to Gemma via Google AI API and streams back notes.

    Signals
    -------
    chunk_ready : str
        Emitted for each streaming fragment as it arrives.
    done : str
        Emitted once with the complete generated notes.
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

    def run(self) -> None:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)
            model = genai.GenerativeModel(self._model_id)

            prompt = build_prompt(
                self._course_name,
                self._lecture_num,
                self._date,
                self._transcript,
                self._custom_instruction,
            )

            response = model.generate_content(
                prompt,
                stream=True,
                generation_config=genai.types.GenerationConfig(
                    temperature=self._temperature,
                    max_output_tokens=self._max_tokens,
                ),
            )

            full = ""
            for chunk in response:
                text = chunk.text
                full += text
                self.chunk_ready.emit(text)

            self.done.emit(full)

        except Exception as exc:
            logger.exception("NotesWorker failed")
            self.error.emit(str(exc))
