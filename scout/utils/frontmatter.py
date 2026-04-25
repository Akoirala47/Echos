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
) -> str:
    """Prepend YAML front matter to notes_body and return the full note string.

    tags_template supports the {course_lower} placeholder which is replaced
    with the lowercase course name.
    """
    tags = tags_template.replace("{course_lower}", course.lower())
    front = (
        "---\n"
        f"course: {course}\n"
        f"lecture: {lecture_num}\n"
        f"date: {date}\n"
        f"tags: {tags}\n"
        f"scout_version: {version}\n"
        "---\n\n"
    )
    return front + notes_body
