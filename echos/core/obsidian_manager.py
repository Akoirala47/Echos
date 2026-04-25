from __future__ import annotations

import re
import subprocess
from pathlib import Path


class ObsidianManager:
    """Handles all filesystem operations for the user's Obsidian vault."""

    # ------------------------------------------------------------------
    # Lecture numbering
    # ------------------------------------------------------------------

    def next_lecture_num(self, vault: Path, folder: str) -> int:
        """Return the next lecture number for a course folder.

        Scans vault/folder/ for files matching Lecture-NN.md and returns
        max(N) + 1.  Returns 1 if the folder is missing or empty.
        """
        course_dir = vault / folder
        if not course_dir.exists():
            return 1
        pattern = re.compile(r"^Lecture-(\d+)\.md$", re.IGNORECASE)
        numbers = [
            int(m.group(1))
            for f in course_dir.iterdir()
            if f.is_file() and (m := pattern.match(f.name))
        ]
        return max(numbers) + 1 if numbers else 1

    # ------------------------------------------------------------------
    # Existence check
    # ------------------------------------------------------------------

    def note_exists(self, vault: Path, folder: str, num: int) -> bool:
        return (vault / folder / f"Lecture-{num:02d}.md").exists()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_note(
        self,
        vault: Path,
        folder: str,
        num: int,
        content: str,
        course: str,
        date: str,
    ) -> Path:
        """Write the note to vault/folder/Lecture-NN.md.

        Creates the course subfolder if it does not exist.
        Returns the Path of the written file.
        """
        course_dir = vault / folder
        course_dir.mkdir(parents=True, exist_ok=True)
        note_path = course_dir / f"Lecture-{num:02d}.md"
        note_path.write_text(content, encoding="utf-8")
        return note_path

    # ------------------------------------------------------------------
    # Open in Obsidian
    # ------------------------------------------------------------------

    def open_in_obsidian(self, vault_name: str, file_relative_path: str) -> None:
        """Open the saved note in Obsidian via the obsidian:// URI scheme."""
        from urllib.parse import quote
        encoded_file = quote(file_relative_path, safe="")
        encoded_vault = quote(vault_name, safe="")
        uri = f"obsidian://open?vault={encoded_vault}&file={encoded_file}"
        subprocess.run(["open", uri], check=False)
