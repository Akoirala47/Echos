from __future__ import annotations


def build_prompt(
    course_name: str,
    lecture_num: int,
    date: str,
    transcript: str,
    custom_suffix: str = "",
) -> str:
    """Assemble the full system prompt sent to Gemma for note generation."""
    suffix_block = (
        f"\n\nAdditional instruction: {custom_suffix.strip()}"
        if custom_suffix.strip()
        else ""
    )
    return (
        "You are a precise academic note-taker for computer science.\n"
        "Convert the transcript below into clean Obsidian-compatible markdown notes.\n\n"
        f"Course: {course_name}\n"
        f"Lecture: {lecture_num}\n"
        f"Date: {date}\n\n"
        "Rules:\n"
        f"- Start with: # {course_name} \u00b7 Lecture {lecture_num}\n"
        f"- Second line: *{date}*\n"
        "- ## for main topics, ### for subtopics\n"
        "- Bullet points for all key facts\n"
        "- Code blocks (```) for algorithms, pseudocode, formulas, complexity\n"
        "- Bold (**term**) on first use of every key term\n"
        '- Include a "## Key Takeaways" section at the end\n'
        '- Output only the markdown. No preamble, no "Here are your notes:"\n'
        f"{suffix_block}\n\n"
        f"Transcript:\n{transcript}"
    )
