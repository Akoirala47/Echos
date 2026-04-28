# Scout — Implementation Task List

> Ordered from foundational infrastructure to UI polish. Each task is atomic — a single file or tightly coupled group of files. Complete phases in order; tasks within a phase can parallelise unless noted.

---

## Phase 0 — Repository Bootstrap

- [ ] **T-001** Create repo layout: `scout/`, `scout/ui/`, `scout/ui/widgets/`, `scout/core/`, `scout/config/`, `scout/utils/`, `assets/`, `build/`, `.github/workflows/`
- [ ] **T-002** Write `requirements.txt` (PyQt6, transformers, torch, torchaudio, sounddevice, numpy, huggingface_hub, google-generativeai, soundfile)
- [ ] **T-003** Write `requirements-dev.txt` (py2app, pytest, black, ruff)
- [ ] **T-004** Write `.gitignore` (Python, py2app `build/`+`dist/`, `.env`, HuggingFace cache)
- [ ] **T-005** Add MIT `LICENSE`

---

## Phase 1 — Config & Defaults

- [ ] **T-006** `scout/config/defaults.py` — define `DEFAULT_CONFIG` dict with all keys and default values from SPEC §3.2
- [ ] **T-007** `scout/config/config_manager.py` — `ConfigManager` class:
  - `load() -> dict` — reads `config.json`, merges with defaults, returns defaults on missing file
  - `save(config: dict) -> None` — atomic write (write temp file, rename)
  - `is_first_launch() -> bool` — checks file existence
  - Creates `~/Library/Application Support/Scout/` directory if absent on first save

---

## Phase 2 — Core: Model Manager

- [ ] **T-008** `scout/core/model_manager.py` — `ModelManager` class:
  - `__init__` — detect device (`mps` / `cpu`)
  - `is_cached() -> bool` — uses `try_to_load_from_cache`
  - `download(progress_callback: Callable[[int, int], None])` — `snapshot_download` wrapper; polls cache dir size vs expected 5 GB to drive progress
  - `load()` — `AutoProcessor` + `AutoModelForSpeechSeq2Seq` (or NeMo path); sets `float16` on MPS; calls `model.eval()`
  - `transcribe(audio_chunk: np.ndarray, sample_rate: int) -> str`
  - `is_loaded() -> bool`

---

## Phase 3 — Core: Audio Worker

- [ ] **T-009** `scout/utils/audio_utils.py`:
  - `compute_rms(chunk: np.ndarray) -> float` — returns 0.0–1.0 normalised RMS
  - `split_into_chunks(buffer: np.ndarray, chunk_samples: int, overlap_samples: int) -> List[np.ndarray]`
  - `deduplicate_overlap(prev_text: str, new_text: str) -> str` — removes repeated words at transcript boundary

- [ ] **T-010** `scout/core/audio_worker.py` — `AudioWorker(QThread)`:
  - Signals: `transcript_chunk(str)`, `audio_level(float)`, `error(str)`
  - Opens `sounddevice.InputStream` (16kHz, mono, float32) in `run()`
  - Accumulates samples into rolling buffer; emits `audio_level` at ~30fps via `QTimer` on main thread
  - Every `chunk_seconds` of audio: calls `model_manager.transcribe()`, emits `transcript_chunk`
  - Slots: `pause()`, `resume()`, `stop()` — thread-safe via `threading.Event`

---

## Phase 4 — Core: Notes Worker

- [ ] **T-011** `scout/utils/markdown.py`:
  - `build_prompt(course_name, lecture_num, date, transcript, custom_suffix) -> str` — assembles the full Gemma system prompt from SPEC §4.2

- [ ] **T-012** `scout/core/notes_worker.py` — `NotesWorker(QThread)`:
  - Constructor: `transcript`, `course_name`, `lecture_num`, `date`, `api_key`, `model_id`, `temperature`, `max_tokens`, `custom_instruction`
  - Signals: `chunk_ready(str)`, `done(str)`, `error(str)`
  - `run()`: `genai.configure` → `GenerativeModel.generate_content(stream=True)` → emit each chunk → emit `done`
  - Catches `google.api_core.exceptions` subclasses, emits `error`

---

## Phase 5 — Core: Obsidian Manager

- [ ] **T-013** `scout/core/obsidian_manager.py` — `ObsidianManager` class:
  - `next_lecture_num(vault: Path, folder: str) -> int`
  - `save_note(vault, folder, num, content, course, date) -> Path`
  - `open_in_obsidian(vault_name, file_relative_path)`
  - `note_exists(vault, folder, num) -> bool`

- [ ] **T-014** `scout/utils/frontmatter.py`:
  - `inject_frontmatter(notes_body: str, course: str, lecture_num: int, date: str, tags_template: str, version: str) -> str` — prepends YAML block to notes

---

## Phase 6 — UI: Widgets

- [ ] **T-015** `scout/ui/widgets/waveform.py` — `WaveformWidget(QWidget)`:
  - Custom `QPainter` rendering of N vertical bars
  - `set_level(rms: float)` slot — updates bar heights based on real RMS
  - Animates smoothly with `QPropertyAnimation` or manual lerp on `paintEvent`
  - Respects `show_waveform` setting (shows flat line when off)

- [ ] **T-016** `scout/ui/widgets/course_item.py` — `CourseItem(QWidget)`:
  - Displays colour dot + course name
  - Used as `QListWidget` item delegate

- [ ] **T-017** `scout/ui/widgets/model_progress.py` — `ModelProgressWidget(QWidget)`:
  - Progress bar + "X.X GB of 5.0 GB · N MB/s · N min left" label
  - `update(bytes_done, bytes_total, speed_bps)` method
  - "Background" button emits `backgroundRequested` signal

---

## Phase 7 — UI: Onboarding Wizard

- [ ] **T-018** `scout/ui/onboarding.py` — `OnboardingWizard(QWizard)` — 3 pages:
  - **Page 1** `WelcomePage`: static text + "Get Started" button
  - **Page 2** `SetupPage`: vault path `QLineEdit` + "Browse…" `QPushButton` (`QFileDialog.getExistingDirectory`); Google API key `QLineEdit` (echo mode Password); "Get a free key →" label linking to `aistudio.google.com/apikey`; async key validation (one-shot `NotesWorker` call with minimal prompt) — shows ✓ or error inline
  - **Page 3** `DownloadPage`: embeds `ModelProgressWidget`; launches `ModelDownloadWorker`; "Background" dismisses wizard; next button enabled only on `done` signal
  - On completion: saves vault path + API key via `ConfigManager.save()`

- [ ] **T-019** `ModelDownloadWorker(QThread)` — placed in `scout/core/model_manager.py`:
  - Calls `ModelManager.download()`, polls progress, emits `progress(int, int)`, `done()`, `error(str)`

---

## Phase 8 — UI: Settings Window

- [ ] **T-020** `scout/ui/settings_window.py` — `SettingsWindow(QDialog)` — 4 tabs:
  - **General**: vault path picker, auto-open toggle, prevent-sleep toggle, show-waveform toggle, record shortcut key capture
  - **API Keys**: Google API key field, Gemma model text field, "Test Connection" button
  - **Transcription**: model dropdown (Canary-Qwen only in v1), chunk size slider (3–10s), overlap slider (0–1s), device dropdown, model status label, "Re-download Model" button
  - **Notes**: temperature slider (0.0–1.0), max tokens slider, language dropdown, front matter toggle, tags template text, custom prompt suffix textarea
  - "Save" applies changes via `ConfigManager.save()`; "Cancel" discards

---

## Phase 9 — UI: Main Window Layout

- [ ] **T-021** `scout/ui/sidebar.py` — `SidebarWidget(QWidget)`:
  - `QListWidget` with `CourseItem` delegates
  - Drag-and-drop reorder (Qt internal move mode)
  - "+" button opens `AddCourseDialog` (inline `QDialog`: name field, folder field, colour picker with 8 swatches)
  - Right-click context menu: "Delete Course" with `QMessageBox` confirmation
  - Emits `course_selected(Course)`, `course_added(Course)`, `course_deleted(course_id: str)`, `courses_reordered(List[Course])`

- [ ] **T-022** `scout/ui/record_bar.py` — `RecordBarWidget(QWidget)`:
  - Large record button with 3 visual states (IDLE / RECORDING / PAUSED) per SPEC §5.2
  - `WaveformWidget` inline
  - Elapsed time `QLabel` updated by `QTimer` every second
  - Lecture number `QSpinBox` (editable)
  - Emits `record_clicked()`, `pause_clicked()`

- [ ] **T-023** `scout/ui/transcript_panel.py` — `TranscriptPanel(QWidget)`:
  - `QTextEdit` (editable, monospace-ish)
  - `append_text(text: str)` — appends with subtle fade-in via `QPropertyAnimation` on opacity
  - Toolbar: "Clear", "Export as .txt"
  - `get_text() -> str`

- [ ] **T-024** `scout/ui/notes_panel.py` — `NotesPanel(QWidget)`:
  - Rendered view: `QTextBrowser` with custom CSS stylesheet (h1, h2, code blocks per SPEC §5.3)
  - Raw view: `QTextEdit`
  - Toggle button in panel header switches modes
  - "Generate Notes" button (disabled until recording stopped)
  - "Regenerate" button with optional instruction `QInputDialog`
  - `set_notes(markdown: str)` — converts markdown to HTML via `markdown` stdlib, renders in `QTextBrowser`
  - `append_chunk(text: str)` — appends to raw string then re-renders

- [ ] **T-025** `scout/ui/status_bar.py` — `StatusBarWidget(QWidget)`:
  - Status dot (coloured circle) + status text label
  - Vault path label
  - "Save to Obsidian" `QPushButton`
  - "Open in Obsidian" `QPushButton` (hidden until note saved)
  - `set_status(color: str, text: str)`

- [ ] **T-026** `scout/ui/main_window.py` — `MainWindow(QMainWindow)`:
  - Assembles sidebar + record bar + transcript panel + notes panel + status bar per SPEC §5.1
  - Sets window minimum size 820×560
  - Applies sidebar fixed width 186px with drag-resize splitter
  - Defines menu bar: Scout / File / View / Help menus with all actions and keyboard shortcuts per SPEC §4.7
  - Connects all widget signals to `AppController` slots

---

## Phase 10 — App Controller

- [ ] **T-027** `scout/app.py` — `AppController`:
  - Owns `ConfigManager`, `ModelManager`, `ObsidianManager`, `AudioWorker`, sidebar/panel references
  - State machine: `IDLE → RECORDING → PAUSED → STOPPED → NOTES_GENERATED → SAVED`
  - `on_record_clicked()` — start/stop AudioWorker; toggle Dock badge (red dot via `NSApp.dockTile`)
  - `on_pause_clicked()` — pause/resume AudioWorker
  - `on_transcript_chunk(text)` — appends to TranscriptPanel
  - `on_generate_notes_clicked()` — reads transcript, launches NotesWorker
  - `on_notes_chunk(text)` — calls `notes_panel.append_chunk()`
  - `on_notes_done(text)` — stores notes; enables Save button
  - `on_save_clicked()` — checks overwrite; calls `ObsidianManager.save_note()`; updates status bar
  - `on_course_selected(course)` — updates lecture number via `ObsidianManager.next_lecture_num()`
  - Power assertion: start/stop `NSProcessInfo.processInfo.beginActivityWithOptions` during recording
  - Dock red dot: set via `objc` bridge to `NSApplication.dockTile`

---

## Phase 11 — Entry Point

- [ ] **T-028** `scout/main.py`:
  - `QApplication` init
  - Check `ConfigManager.is_first_launch()` → show `OnboardingWizard` or proceed
  - Load `ModelManager` in a background thread if cached (show "Loading model…" status)
  - If not cached after onboarding background-download choice: disable record button
  - Instantiate `MainWindow` + `AppController`; show window; `app.exec()`

---

## Phase 12 — Build Infrastructure

- [ ] **T-029** `assets/icon.icns` + `assets/icon_512.png` — create app icon (1024×1024 source, export to `.icns` using `iconutil`)
- [ ] **T-030** `assets/dmg_background.png` — 540×380px background image for DMG window
- [ ] **T-031** `build/setup.py` — py2app config per SPEC §10 (plist keys, packages list, excludes)
- [ ] **T-032** `build/entitlements.plist` — audio-input + user-selected read-write + network-client entitlements
- [ ] **T-033** `build/build.sh` — `py2app` → `create-dmg` script per SPEC §10; `chmod +x`

---

## Phase 13 — CI/CD

- [ ] **T-034** `.github/workflows/build.yml` — GitHub Actions on `v*` tags:
  - `macos-14` runner (Apple Silicon)
  - Python 3.11 setup
  - `pip install -r requirements.txt -r requirements-dev.txt`
  - Run `build/build.sh`
  - Upload `dist/Scout-*.dmg` as release asset via `softprops/action-gh-release`

---

## Phase 14 — Logging

- [ ] **T-035** Add Python `logging` setup in `main.py`:
  - Rotating file handler to `~/Library/Logs/Scout/scout.log` (10 MB × 3 backups)
  - Console handler (DEBUG level) in dev; INFO in production
  - Log AudioWorker chunk timings, NotesWorker API latency, save operations

---

## Phase 15 — Tests

- [ ] **T-036** `tests/test_config_manager.py` — unit tests: load defaults on missing file, load+save roundtrip, `is_first_launch` logic, atomic write (simulate crash mid-write)
- [ ] **T-037** `tests/test_audio_utils.py` — unit tests: `compute_rms` boundary values, `split_into_chunks` with overlap, `deduplicate_overlap` edge cases
- [ ] **T-038** `tests/test_frontmatter.py` — unit tests: correct YAML block generation, tags template rendering, special characters in course name
- [ ] **T-039** `tests/test_obsidian_manager.py` — unit tests with `tmp_path`: `next_lecture_num` with empty/existing folder, `save_note` creates directory, file content matches expected, overwrite not triggered for new file
- [ ] **T-040** `tests/test_markdown_prompt.py` — unit tests: prompt includes transcript, course name, date, custom suffix appended correctly
- [ ] **T-041** `tests/test_model_manager_cache.py` — unit test `is_cached()` with monkeypatched `try_to_load_from_cache`

---

## Phase 16 — Polish & Edge Cases

- [ ] **T-042** Implement `prevent_sleep` power assertion via `pyobjc` `NSProcessInfo` call in `AppController`; guard with `try/except ImportError` for non-macOS
- [ ] **T-043** Implement Dock red dot badge during recording via `pyobjc` `NSDockTile`
- [ ] **T-044** Wire `⌘R` / `⌘P` keyboard shortcuts through `QShortcut` in `MainWindow`; respect user-configured shortcut from settings
- [ ] **T-045** "Export Transcript" action in File menu — `QFileDialog.getSaveFileName` → write `.txt`
- [ ] **T-046** "Copy to Clipboard" action in Notes panel — `QApplication.clipboard().setText(notes)`
- [ ] **T-047** Apply dark mode support — use `QApplication.palette()` adaptation; test all panels in dark mode
- [ ] **T-048** Window minimum size enforcement (820×560) and sidebar drag-resize splitter
- [ ] **T-049** Error dialog helper `show_error(parent, title, message)` used consistently across all error paths in SPEC §5
- [ ] **T-050** README.md — badges, install instructions (DMG drag-install), first-launch walkthrough, developer setup (`pip install -r requirements-dev.txt`), build instructions, "Without Developer account" Gatekeeper note

---

---

## Phase 17 — UI Overhaul (mockup → production)

> Recreate the `ui-mockup/site/` design exactly. Warm parchment palette, new record-bar UX
> (Start/Pause/Resume — never Stop), End Session confirmation, vault-tree sidebar, status-bar
> action buttons. Implement in order; each task is a self-contained file change.

- [x] **T-051** `echos/utils/theme.py` — replace grey palette with warm parchment colours; add `window_bg`, `panel_bg`, `statusbar_bg`, `border`, `border_soft`, `accent`, `recording_color`, `paused_color`, `ready_color`, `text`, `text_muted`, `text_faint` helpers for both light and dark modes.
- [x] **T-052** `echos/main.py` — apply global QSS baseline (font: Inter/-apple-system, base background) on QApplication after palette is set.
- [x] **T-053** `echos/ui/record_bar.py` — complete redesign: two-row layout (header row: colour dot + topic name + breadcrumb + Session N input; control row: PrimaryButton + status pill + waveform + timer). PrimaryButton cycles Start→Pause→Resume; never shows Stop. Add `end_session_clicked` signal for status bar.
- [x] **T-054** `echos/ui/widgets/waveform.py` — increase bar count to 36, use accent color from theme, keep staggered animation.
- [x] **T-055** `echos/ui/status_bar.py` — add `end_session_clicked` + `new_session_clicked` signals; show End Session pill during recording/paused; show New Session + Save + Open buttons per state; warm background colour.
- [x] **T-056** `echos/ui/sidebar.py` — full redesign: vault-name header; collapsible VAULT section with live disk tree (VaultTreeWidget); collapsible TOPICS section (existing courses as coloured shortcuts); "Rec here" hover pill on vault folders; collapsible section chevrons; warm background.
- [x] **T-057** `echos/app.py` — wire new signals: `end_session_clicked` → confirm dialog → `_stop_recording`; `new_session_clicked` → `_on_new_recording`; `vault_folder_selected` → update save target; update title-bar format to "Echos — {topic} — {path}"; state labels updated.
- [x] **T-058** `echos/ui/main_window.py` — remove standalone course-header bar (it is now part of record bar); update `update_course_header` to set window title only; remove layout references to deleted widget.
- [x] **T-059** `echos/ui/transcript_panel.py` — new panel-header style (10 px uppercase label + ghost mini-buttons, `--border-soft` divider); warm panel background; placeholder text updated.
- [x] **T-060** `echos/ui/notes_panel.py` — new panel-header style matching transcript panel; footer row with Generate/Regenerate + model-name chip; warm background; `_md_to_html` uses updated theme colours.

---

## Dependency Graph (critical path)

```
T-001 → T-006 → T-007
T-007 → T-008 → T-019
T-008 → T-009 → T-010
T-011 → T-012
T-013 → T-014
T-015 → T-016 → T-017
T-018 depends on T-017, T-019
T-020 depends on T-008
T-021 → T-022 → T-023 → T-024 → T-025 → T-026
T-026 + T-010 + T-012 + T-013 → T-027 → T-028
T-028 → T-031 → T-032 → T-033 → T-034
```

Tests (T-036–T-041) can be written in parallel with their corresponding implementation tasks.
Polish tasks (T-042–T-050) can begin once T-028 is complete.

---

## Phase 18 — Addendum Tasks (from ui-mockup/TASKS_ADDENDUM.md)

### Phase 18A — Recording Controls (confirm implementation)

- [x] **T-A51** `echos/app.py` — `_on_record_clicked` handles IDLE→REC + PAUSED→REC only; separate `_on_end_session_requested` with confirm dialog.
- [x] **T-A52** `echos/ui/record_bar.py` — primary button: Start/Pause/Resume, never Stop.
- [x] **T-A53** `echos/ui/status_bar.py` — End Session ghost button (visible in RECORDING/PAUSED).
- [x] **T-A54** `echos/ui/main_window.py` — `File → End Session (⌘⇧E)` menu item wired to controller.
- [x] **T-A55** New Session resets panels and flips state to IDLE.
- [x] **T-A56** Keyboard: `⌘R`=Start/Resume, `⌘P`=Pause, `⌘⇧E`=End Session.
- [ ] **T-A57** `tests/test_app_state_machine.py` — state machine tests.

### Phase 18B — Vault Tree Sidebar

- [x] **T-B58** `echos/core/vault_watcher.py` — VaultWatcher (QFileSystemWatcher) keeping tree in sync.
- [x] **T-B59** `echos/ui/widgets/vault_tree.py` — VaultTreeWidget with hover "Record here" pill.
- [x] **T-B60** `echos/ui/sidebar.py` — split layout: VAULT tree + TOPICS, collapsible.
- [x] **T-B61** Path picker in AddTopicDialog using the vault tree.
- [x] **T-B62** Migration shim: `folder` accepts multi-segment paths; bump config version to 1.1.
- [x] **T-B63** Breadcrumb segments in course header are clickable (scroll tree).
- [x] **T-B64** `next_lecture_num` unit test for nested paths.
- [x] **T-B65** `tests/test_vault_watcher.py`.
- [x] **T-B66** Empty-state messages in vault tree when no vault set / vault empty.

### Phase 18C — Design System

- [x] **T-C67** Light-only theme (`echos/utils/theme.py`) — exact mockup CSS var values.
- [x] **T-C68** Fusion Qt style + warm QPalette applied at startup.
- [x] **T-C69** All UI files use hardcoded light values; no `is_dark_mode()` branching.

---

## Phase 19 — UI Polish & Note Preview

- [x] **T-P70** `echos/ui/sidebar.py` — Fix topic-row select indicator: add `background: transparent` to name/path labels so custom `paintEvent` selection color shows correctly; remove stale `super().paintEvent()` call.
- [x] **T-P71** `echos/ui/widgets/waveform.py` — Distribute bars evenly across full widget width so waveform fills all available space up to the timer label.
- [x] **T-P72** `echos/ui/sidebar.py` — Wire vault `+` button to `_on_create_folder`: prompts for name, creates directory, refreshes tree.
- [x] **T-P73** `echos/main.py` — macOS title-bar integration: `setTitlebarAppearsTransparent_`, `NSWindowTitleHidden`, background color matching `WINDOW_BG`, movable by background.
- [x] **T-P74** `echos/ui/record_bar.py` — Remove `margin-top: 1px` from dot label in `set_topic()` to fix vertical mis-alignment in header row.
- [x] **T-P75** `echos/core/notes_worker.py` — Strip `<thinking>`/`<thought>` LLM reasoning blocks from generated notes before emitting `done` signal.
- [x] **T-P76** `echos/ui/main_window.py` + `echos/ui/sidebar.py` + `echos/app.py` — Note file preview: clicking a `.md` file in the vault tree opens it in a `NotePreviewWidget` (stacked over the recording view) with a "← Back" button to return.
- [x] **T-P77** `assets/create_assets.py` — New Qt-rendered app icon: warm rounded-square background, concentric pastel rings, stylised alien-listener face (mint orbs, golden eyes, teal ear pads).

---

## Phase 20 — Multi-Tab Editor

> All UI in this phase must follow the warm-parchment design language in `echos/utils/theme.py`. See `newversionedition-spec.md §UI Design Language Constraint`.

- [x] **T-E01** `echos/utils/theme.py` — Add tab-specific tokens: `TAB_ACTIVE_UNDERLINE = ACCENT`, `TAB_BG = WINDOW_BG`, `TAB_INACTIVE_TEXT = TEXT_MUTED`. No new background colours — reuse existing tokens only.

- [x] **T-E02** `echos/ui/tab_bar.py` — `EchosTabBar(QTabBar)`:
  - `WINDOW_BG` background, `BORDER_SOFT` 1px bottom edge, `ACCENT` 2px underline on active tab.
  - First tab ("Echoes") has no close button — override `tabButton` to return `None` for index 0.
  - All other tabs: ×-button (12px, `TEXT_FAINT`), hover darkens to `TEXT`.
  - Tab text: `TEXT` (active), `TEXT_MUTED` (inactive). Font size 12px, weight 500.
  - Emits `file_tab_close_requested(path: str)`.

- [x] **T-E03** `echos/ui/editor_tab.py` — `EditorTab(QWidget)`:
  - Wraps a `QWebEngineView` loading a local `echos/assets/editor.html` page.
  - Three modes toggled by a segmented control in the tab's toolbar row (32px header, same pattern as other panel headers):
    - **Preview** — `marked.js` renders markdown; `PANEL_BG` background; styled with `notes_css()` from `theme.py`.
    - **Raw** — CodeMirror 6 in read-only mode; `PANEL_BG` bg; gutter `SIDEBAR_BG`; selection `SELECTED`; cursor `ACCENT`.
    - **Edit** — CodeMirror 6 editable; same colours as Raw.
  - `load_file(path: str)` — reads file, passes content + initial mode to the web page via `QWebEngineView.page().runJavaScript`.
  - `get_content() -> str` — retrieves current editor content via JS bridge.
  - `save_file()` — writes content back to disk atomically (write temp, rename); emits `file_saved(path: str)`.
  - `set_mode(mode: Literal["preview", "raw", "edit"])` — communicates mode change to JS.
  - Emits: `content_changed()`, `file_saved(path: str)`.

- [x] **T-E04** `echos/assets/editor.html` — Self-contained HTML/JS/CSS page served locally:
  - Bundles CodeMirror 6 (codemirror, @codemirror/lang-markdown, @codemirror/view) and `marked.js` — all vendored into `echos/assets/vendor/` (no CDN calls).
  - Exposes a `window.echos` JS API: `setContent(text)`, `getContent()`, `setMode(mode)`.
  - Python↔JS bridge via `QWebChannel` (`qwebchannel.js` vendored): `EchosWebBridge` QObject with `content_changed` signal and `file_saved` slot.
  - Background `PANEL_BG` (`#ffffff`), gutter `SIDEBAR_BG` (`#f1efe8`), selection highlight `SELECTED` (`rgba(194,65,12,0.10)`), cursor `ACCENT` (`#c2410c`).

- [x] **T-E05** `echos/ui/tab_manager.py` — `TabManager`:
  - Owns a `QTabWidget` using `EchosTabBar`.
  - Index 0 is always the Echoes tab (the existing recording/notes `QSplitter` view) — never closed.
  - `open_file(path: str)` — if path already open, focus that tab; otherwise create new `EditorTab`, add tab with filename as label, set focus.
  - `close_tab(index: int)` — if tab has unsaved changes, show confirmation dialog (warm-styled `QMessageBox` matching `WINDOW_BG` + `TEXT`); remove tab.
  - `current_tab() -> EditorTab | None`.
  - Tracks `{path → tab_index}` mapping.

- [x] **T-E06** `echos/ui/main_window.py` — integrate tab system:
  - Replace the central `QSplitter` with `TabManager.tab_widget`.
  - Wire sidebar vault-tree file-click signal (`file_selected(path)`) → `tab_manager.open_file(path)`.
  - Remove the stacked `NotePreviewWidget` overlay (T-P76) — file preview now opens as a proper editor tab instead.
  - Keep the Echoes tab (index 0) as the default/home view.

- [x] **T-E07** `tests/test_tab_manager.py` — unit tests: open file creates tab, second open of same file focuses existing tab, Echoes tab cannot be closed, close with unsaved changes triggers dialog.

---

## Phase 21 — Graph Canvas (Brain View)

> Background `CANVAS_BG = "#1c1b17"` (add to `theme.py`). All overlay UI uses standard warm tokens on `PANEL_BG` cards. Transitions: 150ms opacity fade for UI elements, spring-physics settle for force simulation.

- [x] **T-G01** `echos/utils/theme.py` — Add `CANVAS_BG = "#1c1b17"`, `CANVAS_NODE_DEFAULT = "#f6f5f1"`, `CANVAS_EDGE_STRONG = ACCENT`, `CANVAS_EDGE_WEAK = BORDER`, `CANVAS_LABEL = TEXT_FAINT`. Graph domain-cluster palette (6 colours, warm + muted tones): add as `DOMAIN_PALETTE = [...]` list.

- [x] **T-G02** `echos/assets/graph.html` — Self-contained D3 v7 force-directed graph page (D3 vendored into `echos/assets/vendor/`):
  - Canvas background `CANVAS_BG`. Dot-grid overlay (subtle, 20px spacing, `rgba(255,255,255,0.04)` dots).
  - **File nodes**: circles (r=7), filled by primary domain colour from `DOMAIN_PALETTE`. Label below node in 11px `TEXT_FAINT`-equivalent (`#a09e93`). On hover: grow to r=9 (150ms ease), show tooltip card (filename + fingerprint concepts) on `PANEL_BG` (`#ffffff`) with `BORDER_SOFT` border + `TEXT` text.
  - **Directory regions**: convex hulls (`d3.polygonHull`) drawn as filled polygons (`CANVAS_BG` +8% lightness fill, `BORDER`-equivalent stroke `rgba(220,218,207,0.3)`). Directory name label in 10px uppercase `TEXT_FAINT`-equivalent. Not clickable.
  - **Edges**: cubic bezier curves. Three visual types — concept-overlap (solid, 1.5px, domain colour at 60% opacity), vector-similarity (dashed 4/3, 1px, `BORDER`-equivalent), wikilink (solid, 2px, `ACCENT`-equivalent with arrowhead marker). Edge opacity scales linearly with `strength` (0.0–1.0 → 20%–80% opacity).
  - **Force simulation**: `d3.forceSimulation` with `forceLink` (distance 80), `forceManyBody` (strength -120), `forceCollide` (r=14), `forceCenter`.
  - **Zoom + pan**: `d3.zoom` on the SVG container. Scroll to zoom, drag to pan.
  - **JS API** (via `QWebChannel`): `loadGraph(data)` — accepts `{nodes: [...], edges: [...]}` JSON; `expandDirectory(dirId)` — triggers fractal expansion; `collapseDirectory(dirId)`.
  - `window.echosBridge` callbacks: `onNodeClicked(filePath)`, `onReady()`.

- [x] **T-G03** `echos/assets/graph.html` (fractal expansion):
  - Collapsed directories show as a single dim cluster node. Clicking a directory node calls `expandDirectory`.
  - Children spawn at parent centroid position with zero velocity + outward radial impulse (angle = 2π × i/n + jitter).
  - Opacity transition 0→1 over 300ms (CSS transition on the SVG elements).
  - Force simulation `alpha` restarted at 0.5, decays naturally — children settle via spring physics.
  - Collapse: children fade out (opacity 1→0, 200ms), then are removed from the DOM + simulation.
  - Directory hull polygon redraws live as nodes move (re-computed on each `tick`).

- [x] **T-G04** `echos/ui/graph_canvas.py` — `GraphCanvasWidget(QWidget)`:
  - Wraps `QWebEngineView` loading `echos/assets/graph.html`.
  - `QWebChannel` bridge: `EchosGraphBridge(QObject)` with `node_clicked(path: str)` signal and `load_graph(json_str: str)` slot.
  - `set_graph_data(nodes: list, edges: list)` — serialises to JSON, calls `loadGraph` via JS.
  - `expand_directory(dir_id: str)` / `collapse_directory(dir_id: str)` — calls JS.
  - Toolbar overlay (floating `QWidget` atop the web view, top-left): "← Back" ghost button (`PANEL_BG` bg, `BORDER_SOFT` border, `TEXT` text, 6px radius, 8px padding). Clicking emits `back_requested`.
  - Toolbar also shows vault name label (`TEXT_FAINT`, 11px) and a search field (`PANEL_BG`, `BORDER_SOFT` border, `TEXT` placeholder) that filters visible nodes by name.

- [x] **T-G05** `echos/ui/main_window.py` + `echos/ui/sidebar.py` — wire graph view transition:
  - Sidebar vault-name header now has the vault icon as a clickable button. Clicking it emits `graph_view_requested`.
  - `MainWindow` stacks `GraphCanvasWidget` over the tab layout (using `QStackedWidget` or `raise_()`). Show on `graph_view_requested`, hide on `GraphCanvasWidget.back_requested`.
  - Transition: fade in/out using `QGraphicsOpacityEffect` + `QPropertyAnimation` (150ms).

- [x] **T-G06** `echos/app.py` — wire graph data:
  - `_on_graph_view_requested()` — pulls nodes + edges from `VaultIndex`, calls `graph_canvas.set_graph_data(...)`. Show only indexed files; unindexed files shown as grey placeholder nodes.
  - `_on_graph_node_clicked(path)` — calls `tab_manager.open_file(path)`, hides graph view.

- [x] **T-G07** `tests/test_graph_canvas.py` — unit tests: `set_graph_data` serialises correctly, back button emits `back_requested`, node-click signal propagates.


---

## Phase 22 — Fingerprint System

- [x] **T-F01** `echos/utils/theme.py` — No new UI tokens needed for this phase.

- [x] **T-F02** `echos/core/fingerprint.py` — `FingerprintEngine`:
  - `generate(note_body: str, existing_fingerprints: list[str], api_key: str, model_id: str) -> Fingerprint`
  - `Fingerprint` dataclass: `concepts: list[str]` (5–8 terms), `domains: list[str]` (2–3 broad clusters), `content_hash: str` (first 4 chars of SHA-256 of note body).
  - `to_string() -> str` — encodes as `"concepts:[a,b,c] | domain:[x,y] | hash:ab3f"` (≤100 chars).
  - `from_string(s: str) -> Fingerprint` — parses the compact string format.
  - LLM call: passes note body + all existing fingerprint strings to the Google Generative AI API (same `api_key` + `model_id` as notes generation). System prompt instructs the model to (a) prefer reusing existing concept terms before minting new ones, (b) return only the fingerprint JSON object, no preamble.
  - Pre-filter: before calling the LLM, `EmbeddingEngine.top_k_similar(concepts_string, k=20)` narrows which fingerprints to pass (see T-F03). If vault has ≤30 notes, skip pre-filter and pass all.
  - Vocabulary guard: if a new concept term would push the unique concept count beyond 200, attempt consolidation via a second LLM call (merge near-synonyms) before accepting the new term.

- [x] **T-F03** `echos/core/embeddings.py` — `EmbeddingEngine`:
  - Uses `sentence-transformers/all-MiniLM-L6-v2` (22 MB) via the `sentence-transformers` package.
  - `embed(text: str) -> np.ndarray` — returns 384-dim float32 vector.
  - `top_k_similar(query_text: str, k: int) -> list[str]` — loads all stored vectors from `VaultIndex`, computes cosine similarity, returns top-k note IDs.
  - Model is loaded lazily on first call and cached in memory. Emits a `QThread` signal if loaded on first use so the UI can show a status indicator.
  - Handles `ImportError` gracefully if `sentence-transformers` is not installed — falls back to passing all fingerprints (no pre-filter).

- [x] **T-F04** `echos/core/notes_worker.py` — extend post-generation pipeline:
  - After `done` signal is assembled, trigger `FingerprintEngine.generate(...)` in the same worker thread.
  - Inject the fingerprint into the note's YAML frontmatter via `inject_frontmatter` (update `echos/utils/frontmatter.py` to accept an optional `fingerprint: str` kwarg).
  - Emit the updated note body (with fingerprint in frontmatter) via the existing `done` signal — callers receive the fingerprint-annotated note transparently.

- [x] **T-F05** `echos/utils/frontmatter.py` — add `fingerprint` field to YAML block:
  - If `fingerprint` kwarg is provided, append `fingerprint: "{fingerprint_string}"` line to the YAML block.
  - Existing callers not passing `fingerprint` are unaffected (default `None`).

- [x] **T-F06** `tests/test_fingerprint.py` — unit tests: `Fingerprint.to_string` / `from_string` roundtrip, compact string ≤100 chars, vocabulary guard triggers consolidation at 201 concepts, pre-filter skipped for ≤30 notes.

---

## Phase 23 — Indexing System

- [x] **T-I01** `echos/core/vault_index.py` — `VaultIndex`:
  - SQLite database at `{vault_root}/.echoes/vault.index.db`. Creates `.echoes/` on first use.
  - Schema:
    - `notes(id TEXT PK, path TEXT UNIQUE, modified_at REAL, content_hash TEXT, fingerprint_text TEXT, vector_blob BLOB, dirty INTEGER DEFAULT 0)`
    - `edges(source_id TEXT, target_id TEXT, strength REAL, reason TEXT, edge_type TEXT, created_at REAL, PRIMARY KEY(source_id, target_id))`
    - `tags(note_id TEXT, tag TEXT, source TEXT CHECK(source IN ('llm','user')), PRIMARY KEY(note_id, tag))`
  - Methods: `upsert_note(...)`, `set_dirty(path)`, `get_dirty_notes() -> list`, `upsert_edge(...)`, `delete_outgoing_edges(note_id)`, `get_edges(note_id) -> list`, `get_all_nodes() -> list`, `get_all_edges() -> list`, `clear_index()`.
  - All writes are wrapped in transactions. Connection is kept open for the process lifetime (single `sqlite3.Connection`, thread-lock protected).

- [x] **T-I02** `echos/core/index_worker.py` — `IndexWorker(QThread)`:
  - Signals: `progress(done: int, total: int)`, `note_indexed(path: str)`, `error(msg: str)`, `finished()`.
  - Constructor: `vault_index: VaultIndex`, `embedding_engine: EmbeddingEngine`, `fingerprint_engine: FingerprintEngine`.
  - `run()`: process `vault_index.get_dirty_notes()` in batches of 20–30. For each batch:
    1. Read note content from disk.
    2. Compute embedding via `EmbeddingEngine.embed(fingerprint_concepts_string)`, store vector in DB.
    3. Call `FingerprintEngine.generate(...)`, store fingerprint text in DB.
    4. Delete outgoing edges for this note, recompute via LLM connection list, store new edges.
    5. Set `dirty=0` on the note, emit `note_indexed`.
  - Slots: `stop()` — sets a threading.Event; worker exits cleanly after finishing the current batch.

- [x] **T-I03** `echos/core/vault_watcher.py` — extend existing `VaultWatcher`:
  - On file change event: call `vault_index.set_dirty(path)` and enqueue for re-indexing.
  - Debounce: coalesce rapid saves (e.g. 10 saves in 2s) — only enqueue once after a 30s quiet period using a `QTimer` one-shot.
  - On file delete: remove the note row and all its edges from the index.
  - `VaultWatcher` takes `vault_index: VaultIndex | None = None` in its constructor (backwards-compatible default).

- [x] **T-I04** `echos/app.py` — wire indexing into app lifecycle:
  - On vault path set / vault watcher start: instantiate `VaultIndex`, `EmbeddingEngine`, `FingerprintEngine`, `IndexWorker`.
  - On first launch (index missing or empty): run full vault scan — walk vault, `upsert_note` with `dirty=1` for every `.md` file, then start `IndexWorker`.
  - Show a non-blocking status bar message "Indexing vault… N/M" while `IndexWorker` is running, using `IndexWorker.progress` signal. Dismiss on `finished`.
  - On `IndexWorker.error`: log warning, continue (indexing is best-effort, never blocks recording).

- [x] **T-I05** `tests/test_vault_index.py` — unit tests with `tmp_path`: schema creation, `upsert_note` + `get_dirty_notes`, `upsert_edge` + `get_all_edges`, `delete_outgoing_edges`, transaction rollback on error.

- [x] **T-I06** `tests/test_index_worker.py` — unit tests: batch processing marks notes clean, `stop()` exits cleanly mid-batch, error in one note does not abort the batch.

---

## Phase 24 — Graph Connection Rendering

> Consumes the data produced by Phases 22–23. No new UI tokens — uses `DOMAIN_PALETTE` and `CANVAS_*` tokens from T-G01.

- [x] **T-R01** `echos/core/connection_resolver.py` — `ConnectionResolver`:
  - `resolve(vault_index: VaultIndex) -> tuple[list[NodeData], list[EdgeData]]`
  - `NodeData`: `id`, `path`, `label` (filename without extension), `domain` (primary domain from fingerprint), `color` (from `DOMAIN_PALETTE` by domain index), `dir_id` (parent directory path).
  - `EdgeData`: `source`, `target`, `strength` (0.0–1.0), `edge_type` (one of `"concept"`, `"vector"`, `"wikilink"`), `reason`.
  - Edge type resolution rules:
    - `"wikilink"`: note body contains `[[target-name]]` literal.
    - `"concept"`: two notes share ≥1 concept label in their fingerprints.
    - `"vector"`: cosine similarity of stored vectors ≥ 0.8 (and not already a concept edge).
  - For multi-type connections between the same pair: keep the highest-priority type (wikilink > concept > vector) as the single edge, store as the edge_type.
  - `strength` for concept edges = shared concept count / max(total concepts in either note). For vector edges = cosine similarity value. For wikilink edges = 1.0.

- [x] **T-R02** `echos/assets/graph.html` — update edge rendering to match the three visual types:
  - `"concept"` → solid stroke, 1.5px, domain colour at 60% opacity.
  - `"vector"` → `stroke-dasharray: 4,3`, 1px, `rgba(220,218,207,0.6)` (`BORDER`-equivalent).
  - `"wikilink"` → solid, 2px, `#c2410c` (`ACCENT`), with an SVG `<marker>` arrowhead (6×4px triangle, same colour).
  - Opacity animated: transition on `stroke-opacity` when `strength` changes (200ms ease).
  - Node colour: set by `data.color` field passed from `ConnectionResolver`.

- [x] **T-R03** `echos/assets/graph.html` — node domain-colour grouping:
  - Nodes receive `fill` from `data.color` (one of `DOMAIN_PALETTE` colours).
  - A subtle drop-shadow filter on hovered node (`filter: drop-shadow(0 2px 6px rgba(0,0,0,0.4))`).
  - Directory hull polygon fill uses the most common domain colour among its children at 8% opacity + `BORDER`-equivalent stroke.

- [x] **T-R04** `echos/app.py` — wire `ConnectionResolver` into graph view:
  - `_on_graph_view_requested()` calls `ConnectionResolver.resolve(vault_index)`, passes result to `graph_canvas.set_graph_data(nodes, edges)`.
  - Data is recomputed each time the graph view is opened (cheap — just reads from SQLite).

- [x] **T-R05** `tests/test_connection_resolver.py` — unit tests: wikilink detection, concept-overlap strength formula, vector-similarity threshold, multi-type deduplication (wikilink wins), empty vault returns empty lists.

---

## Phase 25 — Bug Fixes (BF-01 / BF-02 / BF-03)

> See SPEC §9 for root-cause analysis and fix plans.

- [ ] **T-X01** `echos/utils/markdown.py` — add `build_continuation_prompt()` for second-and-later transcript chunks: receives `session_name`, `session_num`, `date`, `transcript_chunk`, `chunk_idx`, `total_chunks`, `notes_tail` (last 400 chars of notes so far); instructs the model to extend, not repeat.

- [ ] **T-X02** `echos/core/notes_worker.py` — chunked generation + stream thinking filter:
  - Add `CHUNK_CHAR_LIMIT = 3_500` constant.
  - Add `_split_transcript(text, limit) -> list[str]` splitting on `\n\n` then `. ` boundaries.
  - Modify `run()`: iterate chunks; first uses `build_prompt`, rest use `build_continuation_prompt`; accumulate `full_notes`; emit `chunk_ready` only when no unclosed `<thinking>` block is present (delta computed via `_strip_thinking(full)[emitted_len:]`); emit `done` with total stripped notes after all chunks.

- [ ] **T-X03** `echos/ui/notes_panel.py` + `echos/ui/editor_tab.py` — fix `_md_to_html()` in both files:
  - Add `_strip_frontmatter(text) -> str` (strips `---` … `---` YAML block).
  - Remove `"nl2br"` from the `markdown.markdown()` extensions list.
  - Call `_strip_frontmatter()` before passing text to `markdown.markdown()`.
