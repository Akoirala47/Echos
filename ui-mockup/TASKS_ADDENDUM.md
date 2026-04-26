# Echos — TASKS Addendum (April 2026)

> Implementation tasks for `SPEC_ADDENDUM.md`. Append to existing TASKS.md;
> all task IDs continue from T-050.

---

## Phase A — Recording Controls Refactor

- [ ] **T-051** `echos/app.py` — split `AppState` semantics:
  - Remove the "primary button toggles record/stop" code path in
    `_on_record_clicked`.
  - Add `_on_end_session()` handler.
  - `_on_record_clicked` now only handles IDLE→RECORDING.
  - `_on_pause_clicked` handles RECORDING↔PAUSED only (never stops).
  - Confirm dialog in `_on_end_session()` per SPEC Addendum §A.

- [ ] **T-052** `echos/ui/record_bar.py` — refactor button states:
  - Drop the inline "Pause" sub-button.
  - Primary button is now stateful: Start → Pause → Resume.
  - Remove the "Stop Recording" label entirely.
  - Add new visual treatment for `paused` (green Resume) and
    `recording` (amber Pause) states.
  - Keep waveform + timer + lecture spin behaviour.

- [ ] **T-053** `echos/ui/status_bar.py` — add **End Session** button:
  - Visible whenever state ∈ {RECORDING, PAUSED}; hidden otherwise.
  - Ghost style (no fill, subtle border) so it never competes with
    Save to Obsidian.
  - Right-aligned, left of "Save to Obsidian".
  - Emits `end_session_requested` signal.

- [ ] **T-054** `echos/ui/main_window.py` — add menu item:
  - `File → End Session` (`⌘⇧E`).
  - Bind to `AppController._on_end_session()`.

- [ ] **T-055** Add `Start New Session` action that resets the panels and
  flips state back to IDLE without prompting (since STOPPED is already
  terminal).

- [ ] **T-056** Update keyboard shortcut handling:
  - `⌘R` — Start (when IDLE) or Resume (when PAUSED). No-op when RECORDING.
  - `⌘P` — Pause (when RECORDING). No-op otherwise.
  - `⌘⇧E` — End Session (with confirm).

- [ ] **T-057** `tests/test_app_state_machine.py` — new tests covering:
  - Pause/Resume cycles do not finalise the session.
  - End Session is required to transition into STOPPED.
  - End Session shows confirm dialog (mock `QMessageBox`).
  - Start New Session re-enters IDLE.

---

## Phase B — Vault Tree Sidebar

- [ ] **T-058** `echos/core/vault_watcher.py` — `VaultWatcher` class:
  - Wraps `QFileSystemWatcher`; emits `tree_changed` on add/remove/rename.
  - `scan(root: Path) -> dict` returns nested `{name, kind, children}`.
  - Filters to folders + `.md` files; ignores `.obsidian/`, dotfiles.

- [ ] **T-059** `echos/ui/widgets/vault_tree.py` — `VaultTreeWidget`:
  - Custom `QTreeView` subclass with delegate that renders folder/file
    glyphs and the active-target highlight stripe.
  - Signals: `folder_selected(path: str)`, `note_activated(path: str)`,
    `record_here_requested(path: str)`.
  - Hover state shows a small "● Record here" pill on the folder row.
  - Right-click menu per SPEC Addendum §B.

- [ ] **T-060** `echos/ui/sidebar.py` — refactor into split layout:
  - Use `QSplitter(Vertical)` with `VaultTreeWidget` on top, existing
    courses list on bottom.
  - Each section has a small caps header with chevron toggle.
  - Add `+ New Folder` and `⟳ Refresh` controls under the tree.
  - Keep settings button at the very bottom.

- [ ] **T-061** Update `Course` model (SPEC §3.1) — `folder` accepts
  multi-segment paths (`"School/CS446/Lectures"`). Add a path-picker in
  `AddCourseDialog` that opens the vault tree inline so users select a
  destination instead of typing.

- [ ] **T-062** Migration shim in `ConfigManager.load()`:
  - For courses with no `/` in `folder`, leave as-is (vault root).
  - Bump `config.version` to `"1.1"` once migrated.

- [ ] **T-063** `echos/ui/main_window.py` — extend course header to show
  breadcrumb of the current target folder (`›` separator). Click any
  segment to scroll the tree to that folder.

- [ ] **T-064** `echos/core/obsidian_manager.py`:
  - `next_lecture_num` already accepts arbitrary subfolder; add unit
    test for nested paths (`School/CS446/Lectures`).
  - Ensure `save_note` creates intermediate dirs (already does, verify).

- [ ] **T-065** `tests/test_vault_watcher.py` — pytest with `tmp_path`:
  - Tree scan correctness on mixed folder/file fixture.
  - Watcher emits on file add / remove / rename.
  - Dotfiles and `.obsidian/` excluded.

- [ ] **T-066** Polish: empty-state for the tree when vault path unset
  ("Pick a vault in Settings (⌘,)"), and when vault is empty
  ("This vault is empty. Click + New Folder to create one.").

---

## Dependency notes
- Phase A blocks no other work; can ship independently.
- Phase B depends on `T-013` (`ObsidianManager`) which already exists.
- T-061 (path picker dialog) depends on T-059.
- T-063 depends on T-060.

## Done definition
- All Phase A tasks: pause→resume cycles never close a session; End
  Session confirms; menu, status bar, and keyboard all converge on
  the same controller method.
- All Phase B tasks: sidebar shows a live mirror of the vault, tracks
  external Obsidian changes within ~1s, and topics resolve to nested
  folder paths.
