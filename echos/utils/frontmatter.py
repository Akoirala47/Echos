from __future__ import annotations

import re
from datetime import date as _date


def inject_frontmatter(
    notes_body: str,
    course: str,
    lecture_num: int,
    date: str,
    tags_template: str = "[{course_lower}, lecture, notes]",
    version: str = "1.0.0",
    fingerprint: str | None = None,
) -> str:
    """Prepend YAML front matter to notes_body and return the full note string.

    tags_template supports the {course_lower} placeholder which is replaced
    with the lowercase course name.  Any existing YAML front-matter block in
    notes_body is stripped first so callers can call inject_frontmatter safely
    on already-annotated bodies without creating a double block.

    fingerprint — if provided, appended as a ``fingerprint:`` field in the block.
    """
    body = _strip_existing_frontmatter(notes_body)
    tags = tags_template.replace("{course_lower}", course.lower())
    front = (
        "---\n"
        f"course: {course}\n"
        f"lecture: {lecture_num}\n"
        f"date: {date}\n"
        f"tags: {tags}\n"
        f"echos_version: {version}\n"
    )
    if fingerprint:
        front += f'fingerprint: "{fingerprint}"\n'
    front += "---\n\n"
    return front + body


def _strip_existing_frontmatter(text: str) -> str:
    """Remove a leading YAML front-matter block (---…---) if present."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    # Skip past the closing --- and any trailing newlines
    return text[end + 4:].lstrip("\n")
