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
