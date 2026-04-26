from __future__ import annotations

_SYSTEM_INSTRUCTION = """\
You are a concise note-taker. Convert spoken transcripts into clean, structured Obsidian-compatible markdown.

Output ONLY the markdown document \u2014 start immediately with the # title heading.
No preamble, no reasoning, no explanation, no meta-commentary about the transcript.

Structure:
- # Title on the first line
- *Date* on the second line
- ## for main topics, ### for subtopics
- Bullet points for key facts and details
- **Bold** on first use of each key term
- Code blocks for code, formulas, or algorithms (only when present)
- End with a ## Key Takeaways section\
"""


def build_system_instruction(custom_suffix: str = "") -> str:
    """Return the system instruction, optionally extended with a custom focus."""
    if custom_suffix.strip():
        return _SYSTEM_INSTRUCTION + f"\n\nAdditional focus: {custom_suffix.strip()}"
    return _SYSTEM_INSTRUCTION


def build_prompt(
    session_name: str,
    session_num: int,
    date: str,
    transcript: str,
    custom_suffix: str = "",
) -> str:
    """Build the user-turn prompt (transcript + minimal context)."""
    return (
        f"Session: {session_name} \u00b7 {session_num}\n"
        f"Date: {date}\n"
        f"Title heading to use: # {session_name} \u00b7 {session_num}\n\n"
        f"Transcript:\n{transcript}"
    )
