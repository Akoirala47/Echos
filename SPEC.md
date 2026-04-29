# Scout — Product Requirements Document

> Native macOS lecture note-taking app. Local transcription via NVIDIA Canary-Qwen 2.5B (Apple MPS), structured notes via Gemma 4 31B (Google API), saved directly to an Obsidian vault. Distributed as a signed `.dmg`.

---

## 1. Goals & Non-Goals

### Goals (v1)
- Zero-latency local transcription that never sends audio to the cloud
- One-click structured markdown notes from a full lecture transcript
- First-class Obsidian integration (front matter, lecture numbering, vault URI)
- Self-contained `.dmg` — no user-side Python install required
- Signed & notarized for Gatekeeper-free install

### Non-Goals (v1)
- Real-time note generation during recording
- Audio file import (microphone only)
- Windows / Linux support
- Multi-device sync
- Speaker diarization

---

## 2. User Stories

### Onboarding
| ID | Story |
|----|-------|
| US-01 | As a new user I want a guided setup wizard so I can configure my vault, API key, and download the model without touching config files. |
| US-02 | As a new user I want to be able to continue exploring the app while the model downloads in the background. |
| US-03 | As a new user I want the app to validate my Google AI API key before letting me proceed so I don't hit errors later. |

### Course Management
| ID | Story |
|----|-------|
| US-04 | As a student I want to add a course with a name and vault subfolder so my notes are organised automatically. |
| US-05 | As a student I want to delete a course (with confirmation) when I finish a semester. |
| US-06 | As a student I want to reorder courses in the sidebar via drag-and-drop. |
| US-07 | As a student I want to assign a colour to each course for quick visual identification. |
| US-08 | As a student I want the app to auto-detect the next lecture number so I never have to count files manually. |
| US-09 | As a student I want to override the lecture number before recording in case auto-detection is wrong. |

### Recording
| ID | Story |
|----|-------|
| US-10 | As a student I want a single large Start/Stop button (⌘R) so I can start recording without hunting for a control. |
| US-11 | As a student I want a live waveform visualisation so I know the mic is capturing audio. |
| US-12 | As a student I want an elapsed-time counter so I know how long I've been recording. |
| US-13 | As a student I want to pause and resume recording (⌘P) without losing the transcript so far. |
| US-14 | As a student I want the Mac to stay awake during recording so it doesn't sleep mid-lecture. |
| US-15 | As a student I want a red Dock indicator while recording so I can glance at the Dock and confirm capture is active. |

### Transcription
| ID | Story |
|----|-------|
| US-16 | As a student I want the live transcript to update every ~5 seconds so I can verify the model is working. |
| US-17 | As a student I want to edit the transcript before generating notes so I can fix any errors. |
| US-18 | As a student I want to delete sections of the transcript I don't need in my notes. |

### Notes Generation
| ID | Story |
|----|-------|
| US-19 | As a student I want to trigger note generation manually after recording so I can review the transcript first. |
| US-20 | As a student I want notes to stream in incrementally so I don't stare at a blank screen. |
| US-21 | As a student I want a rendered markdown preview so my notes look polished, not like raw text. |
| US-22 | As a student I want to toggle between rendered and raw edit views so I can fine-tune formatting. |
| US-23 | As a student I want to regenerate notes with an optional custom instruction (e.g. "focus on algorithm proofs"). |
| US-24 | As a student I want to edit the generated notes before saving. |

### Saving & Export
| ID | Story |
|----|-------|
| US-25 | As a student I want one-click save to Obsidian with YAML front matter injected automatically. |
| US-26 | As a student I want the app to auto-create the course folder if it doesn't exist. |
| US-27 | As a student I want a confirmation dialog if a file already exists so I don't accidentally overwrite notes. |
| US-28 | As a student I want an "Open in Obsidian" button after saving so I can jump straight to the note. |
| US-29 | As a student I want to export the raw transcript as `.txt` or copy notes to clipboard. |

### Settings
| ID | Story |
|----|-------|
| US-30 | As a power user I want to tune temperature and max tokens for note generation. |
| US-31 | As a power user I want to adjust audio chunk size and overlap to trade latency against accuracy. |
| US-32 | As a power user I want to change the inference device (Auto / MPS / CPU) manually. |
| US-33 | As a power user I want to re-download the model if the weights become corrupt. |
| US-34 | As a user I want to toggle YAML front matter inclusion and customise the tags template. |

---

## 3. Data Models

### 3.1 Course
```json
{
  "id": "string (UUID v4)",
  "name": "string",
  "folder": "string (vault subfolder name)",
  "color": "string (hex, one of 8 presets)"
}
```

Constraints:
- `name` — non-empty, max 64 chars
- `folder` — valid filesystem path segment, auto-derived from `name`, user-editable
- `color` — must be one of the 8 preset hex values

### 3.2 Config (persisted to `config.json`)
```json
{
  "version": "string",
  "vault_path": "string (absolute path)",
  "google_api_key": "string",
  "gemma_model": "string",
  "temperature": "float [0.0–1.0]",
  "max_tokens": "int [1000–16000]",
  "chunk_seconds": "int [3–10]",
  "chunk_overlap": "float [0.0–1.0]",
  "inference_device": "enum: auto | mps | cpu",
  "auto_open_obsidian": "bool",
  "prevent_sleep": "bool",
  "show_waveform": "bool",
  "record_shortcut": "string",
  "include_frontmatter": "bool",
  "frontmatter_tags": "string (template)",
  "custom_prompt_suffix": "string",
  "note_language": "string",
  "courses": "Course[]"
}
```

Default values:

| Field | Default |
|-------|---------|
| `version` | `"1.0"` |
| `gemma_model` | `"gemma-4-31b-it"` |
| `temperature` | `0.2` |
| `max_tokens` | `8192` |
| `chunk_seconds` | `6` |
| `chunk_overlap` | `0.5` |
| `inference_device` | `"auto"` |
| `auto_open_obsidian` | `false` |
| `prevent_sleep` | `true` |
| `show_waveform` | `true` |
| `record_shortcut` | `"Cmd+R"` |
| `include_frontmatter` | `true` |
| `frontmatter_tags` | `"[{course_lower}, lecture, notes]"` |
| `custom_prompt_suffix` | `""` |
| `note_language` | `"English"` |

### 3.3 Session (in-memory only, not persisted)
```
Session:
  course: Course
  lecture_num: int
  audio_buffer: List[np.ndarray]   # accumulated 16kHz float32 chunks
  transcript: str                   # full transcript text
  notes: str                        # generated markdown notes
  recording_state: enum IDLE | RECORDING | PAUSED | STOPPED
  notes_state: enum IDLE | GENERATING | DONE | ERROR
```

### 3.4 Saved Note (`.md` file)
```markdown
---
course: {course.name}
lecture: {lecture_num}
date: {YYYY-MM-DD}
tags: [{course_lower}, lecture, notes]
scout_version: 1.0.0
---

# {course.name} · Lecture {lecture_num}
*{Month DD, YYYY}*

{generated_notes_body}

## Key Takeaways

- ...
```

---

## 4. API Contracts

### 4.1 Internal Qt Signal/Slot Contracts

#### AudioWorker (QThread)
```
Signals emitted:
  transcript_chunk(text: str)     # new transcribed text fragment (~every 6s)
  audio_level(rms: float)         # 0.0–1.0 RMS for waveform, emitted ~30fps
  error(message: str)             # transcription failure for one chunk

Slots (called from main thread):
  start_recording()
  stop_recording()
  pause()
  resume()
```

#### NotesWorker (QThread)
```
Signals emitted:
  chunk_ready(text: str)          # streaming notes fragment
  done(full_text: str)            # complete generated notes
  error(message: str)

Constructor args:
  transcript: str
  course_name: str
  lecture_num: int
  date: str
  api_key: str
  model_id: str
  temperature: float
  max_tokens: int
  custom_instruction: str         # optional, empty string by default
```

#### ModelDownloadWorker (QThread)
```
Signals emitted:
  progress(bytes_done: int, bytes_total: int)
  done()
  error(message: str)
```

### 4.2 Google Generative AI — Notes Generation

**Request**
```
Model:   gemma-4-31b-it
Stream:  True
Config:
  temperature:      0.2 (configurable)
  max_output_tokens: 8192 (configurable)

System prompt:
  You are a precise academic note-taker for computer science.
  Convert the transcript below into clean Obsidian-compatible markdown notes.

  Course: {course_name}
  Lecture: {lecture_num}
  Date: {date}

  Rules:
  - Start with: # {course_name} · Lecture {lecture_num}
  - Second line: *{date}*
  - ## for main topics, ### for subtopics
  - Bullet points for all key facts
  - Code blocks (```) for algorithms, pseudocode, formulas, complexity
  - Bold (**term**) on first use of every key term
  - Include a "## Key Takeaways" section at the end
  - Output only the markdown. No preamble.
  {custom_prompt_suffix}

  Transcript:
  {transcript}
```

**Response handling**
- Iterate `response` stream, emit each `chunk.text` via `chunk_ready` signal
- Accumulate full text, emit via `done` signal when iteration ends
- On `google.api_core.exceptions.GoogleAPIError` → emit `error(str(e))`

### 4.3 HuggingFace Hub — Model Download

```
Function: snapshot_download(
  repo_id="nvidia/canary-qwen-2.5b",
  local_files_only=False
)
Cache dir: ~/.cache/huggingface/hub/

Presence check:
  try_to_load_from_cache("nvidia/canary-qwen-2.5b", "config.json")
  → None means not cached
```

### 4.4 Canary-Qwen Inference

```
Processor: AutoProcessor.from_pretrained("nvidia/canary-qwen-2.5b")
Model:     AutoModelForSpeechSeq2Seq.from_pretrained(
             "nvidia/canary-qwen-2.5b",
             torch_dtype=torch.float16  # mps only
           ).to(device)

Input:  np.ndarray, dtype=float32, shape=(N,), sample_rate=16000
Output: str (transcribed text)

Note: If model card specifies NeMo EncDecMultiTaskModel, use that class instead.
      The chunking, MPS device selection, and signal interface remain unchanged.
```

### 4.5 ObsidianManager — File Operations

```
next_lecture_num(vault: Path, folder: str) -> int
  Scans vault/folder/ for files matching Lecture-\d+\.md
  Returns max(matched numbers) + 1, or 1 if folder empty/missing

save_note(vault: Path, folder: str, num: int,
          content: str, course: str, date: str) -> Path
  Creates vault/folder/ if missing
  Writes vault/folder/Lecture-{num:02d}.md
  Returns written Path

open_in_obsidian(vault_name: str, file_relative_path: str) -> None
  Calls: open obsidian://open?vault={vault_name}&file={file_relative_path}
```

### 4.6 ConfigManager — Persistence

```
load() -> dict
  Reads ~/Library/Application Support/Scout/config.json
  Returns dict merged with defaults (missing keys filled from defaults)
  Returns defaults if file missing

save(config: dict) -> None
  Writes ~/Library/Application Support/Scout/config.json (atomic write)

is_first_launch() -> bool
  Returns True if config.json does not exist
```

---

## 5. Error Handling Matrix

| Scenario | Detection | Response |
|----------|-----------|----------|
| Mic permission denied | `sounddevice.PortAudioError` on stream open | Show dialog with System Settings > Privacy > Microphone link |
| Model not downloaded | `is_cached()` returns False at startup | Disable record button; show "Download model" banner |
| Canary-Qwen chunk failure | Exception in `transcribe()` | Log error; emit error signal; continue next chunk |
| Google API key missing | `google_api_key` empty in config | Disable "Generate Notes" button with tooltip |
| Google API rate limit | `ResourceExhausted` exception | Error dialog with retry button; transcript preserved |
| Google API network error | `ServiceUnavailable` / connection error | "No internet" status bar message; transcript still works |
| Vault path not found | `Path.exists()` False at save time | Warning dialog; offer to pick new vault |
| Vault subfolder missing | `Path.exists()` False before write | Auto-create silently with `Path.mkdir(parents=True)` |
| File already exists | `Path.exists()` True before write | Dialog: Overwrite / Save as Lecture-NN-2.md / Cancel |
| OOM during model load | `torch.cuda.OutOfMemoryError` / `RuntimeError` | Error dialog: close other apps; offer CPU fallback |

---

## 6. Platform Requirements

- **macOS**: 13.0 (Ventura) minimum
- **Hardware**: Apple Silicon (M1+) recommended; Intel supported (CPU inference)
- **Python**: 3.11 (embedded in `.app`, not required from user)
- **Obsidian**: must be installed by user; Scout does not manage the vault
- **Disk**: ~620 MB for app + ~5 GB for model weights (downloaded on first launch)
- **RAM**: 16 GB recommended; 8 GB minimum (CPU-only mode)

---

## 7. Security & Privacy

- API key stored in `config.json` at `~/Library/Application Support/Scout/` (user-only permissions)
- Audio never leaves the device during transcription
- No telemetry or analytics
- `NSMicrophoneUsageDescription` plist key required for mic access
- Network entitlement (`com.apple.security.network.client`) required for Google API calls only


---

## 8. Addendum — April 2026

> Imported from `ui-mockup/SPEC_ADDENDUM.md`.

### 8A. Recording Controls — Separate Pause from End Session

The recording state machine:

```
IDLE ──Start──▶ RECORDING ◀──Resume── PAUSED
                    │   ─────Pause────▶
                    └────End Session──▶ STOPPED  (terminal for that session)
```

- Primary button cycles: **Start Recording → Pause → Resume** (never Stop).
- **End Session** is a separate ghost button in the status bar (right side) + `File → End Session` (`⌘⇧E`). Requires confirm dialog.
- Keyboard: `⌘R` = Start (IDLE) or Resume (PAUSED); `⌘P` = Pause (RECORDING); `⌘⇧E` = End Session.
- After End Session: status bar shows "Session complete" with Generate Notes + Start New Session actions.

### 8B. Sidebar — Vault Tree

The sidebar becomes a two-section panel:
- **VAULT** (top, collapsible): live mirror of the Obsidian vault on disk. Folders with chevrons; `.md` leaves without. Hover on folder shows "● Record here" pill. Right-click: New Subfolder / Rename / Reveal in Finder.
- **TOPICS** (bottom, collapsible): named bookmarks pointing at vault-relative folder paths. Selecting a topic expands the tree to that folder.
- Sections resizable with a drag handle.
- `VaultWatcher` (QFileSystemWatcher) keeps the tree in sync with disk changes.

### 8C. Design System — Light Mode Only

- Warm parchment palette, no dark-mode branching.
- All colours hardcoded from the mockup CSS variables (see `echos/utils/theme.py`).
- Fusion Qt style + custom QPalette so every native widget matches.

---

## 9. Bug Fix Log (Phase 25)

### BF-01 — Chunked Notes Generation (API 500 on long transcripts)

**Root cause**: The Google Generative AI API returns HTTP 500 when a single request exceeds ≈1 000 tokens. Lecture sessions longer than 10–15 minutes routinely produce transcripts in the 1 500–4 000+ token range, making note generation fail entirely for any non-trivial session.

**Fix plan**:
- Add `CHUNK_CHAR_LIMIT = 3_500` constant in `NotesWorker` (≈875 tokens, safely below the 1 000-token threshold).
- Add `_split_transcript(text, limit) -> list[str]` that partitions on double-newline (`\n\n`) boundaries, falling back to the last `. ` within the window when no paragraph break is found.
- For the **first chunk** use `build_prompt()` unchanged.
- For **subsequent chunks** use a new `build_continuation_prompt()` that passes the last 400 chars of accumulated notes as context so the AI continues coherently rather than starting fresh.
- In `NotesWorker.run()`: iterate over chunks, accumulate `full_notes`, stream each chunk's response through `chunk_ready`, then emit `done` once all chunks are processed.
- `fingerprint_engine.generate()` is called once on the entire `full_notes` at the end.

**Files changed**: `echos/core/notes_worker.py`, `echos/utils/markdown.py`.

---

### BF-02 — Thinking Blocks Visible During Streaming

**Root cause**: `_strip_thinking()` is applied only to the final `done` payload. While the API streams, `<thinking>…</thinking>` blocks are emitted verbatim via `chunk_ready`, rendering the model's internal reasoning in the notes panel.

**Fix plan**:
- Track `open_count`/`close_count` of `<thinking|thought>` tags seen so far during streaming.
- Only call `self.chunk_ready.emit(delta)` when tags are balanced (no unclosed thinking block).
- The "delta" is computed as `_strip_thinking(full)[emitted_len:]` on each iteration, so the panel never shows thinking fragments.
- No change to `_strip_thinking()` itself or the `done` path.

**Files changed**: `echos/core/notes_worker.py`.

---

### BF-03 — Preview Renders Raw Markdown Instead of HTML

**Root cause**: Two compounding bugs in `_md_to_html()`:
1. The `nl2br` extension converts all `\n` to `<br>` *before* block-level parsing. This breaks list detection, heading detection, and fenced-code parsing — every `*` item and `##` heading renders as literal text with a `<br>` after it.
2. YAML frontmatter (`---` … `---`) is passed straight to the markdown renderer, which turns each `---` into `<hr>` and renders the YAML key-value pairs as paragraph text.

**Fix plan**:
- Add `_strip_frontmatter(text) -> str` helper: if `text` starts with `---`, find the next `\n---` occurrence and drop everything up to and including it.
- Remove `"nl2br"` from the extensions list in `_md_to_html()`.
- Apply both fixes to the `_md_to_html()` function in **both** `echos/ui/notes_panel.py` and `echos/ui/editor_tab.py` (they share identical implementations).

**Files changed**: `echos/ui/notes_panel.py`, `echos/ui/editor_tab.py`.

---

## 10. Phase 26 — Deprecation: Brain View & Semantic Indexing

> **Audit status**: Triple-checked against live code as of April 2026. All cross-file
> dependencies listed below have been verified by reading every affected file.

### 10.1 Motivation

The Brain/Canvas view (`graph_canvas.py`, `connection_resolver.py`) and the semantic
indexing pipeline (`vault_index.py`, `embeddings.py`, `index_worker.py`) are currently
broken, memory-heavy, and require `sentence-transformers` / `torch` (multi-GB download).
Removing them reduces the app footprint, eliminates startup overhead, and clears the
code surface area before adding the QoL features in Phase 27+.

### 10.2 Files to Delete

| File | Reason |
|------|--------|
| `echos/core/embeddings.py` | `EmbeddingEngine` — sentence-transformers wrapper, used only by fingerprint pre-filter and graph edge computation |
| `echos/core/vault_index.py` | `VaultIndex` — SQLite index, used only by graph and indexing pipeline |
| `echos/core/index_worker.py` | `IndexWorker` — background vault indexer, reads/writes VaultIndex only |
| `echos/core/connection_resolver.py` | `ConnectionResolver` — builds NodeData/EdgeData for graph display, imports VaultIndex + numpy |
| `echos/ui/graph_canvas.py` | `GraphCanvasWidget` — QWebEngineView wrapping `graph.html`, referenced only by MainWindow |

**Note:** `echos/core/fingerprint.py` (`FingerprintEngine` / `Fingerprint`) is **NOT** deleted.
It has no imports of the deleted modules. After Phase 26 it becomes unused (not instantiated in
`app.py`) but leaving the file causes zero runtime issues. It can be cleaned up in a later pass.

### 10.3 `echos/app.py` — Required Changes

This file has the most invasive changes. Every item below must be removed; skipping any one
will cause an `ImportError` or `AttributeError` crash at startup.

#### Imports to remove (top of file)
```python
from echos.core.embeddings import EmbeddingEngine   # DELETE
from echos.core.index_worker import IndexWorker      # DELETE
from echos.core.vault_index import VaultIndex        # DELETE
```
`FingerprintEngine` import can stay or be removed; after `_init_vault_index` is deleted it will
be unreferenced but harmless.

#### Instance variables to remove (inside `__init__`)
```python
self._vault_index: VaultIndex | None = None       # DELETE
self._embedding_engine: EmbeddingEngine | None = None  # DELETE
self._fingerprint_engine: FingerprintEngine | None = None  # DELETE
self._index_worker: IndexWorker | None = None     # DELETE
```

#### Signal connections to remove (inside `_connect_signals`)
```python
w.sidebar.graph_view_requested.connect(self._on_graph_view_requested)  # DELETE
w.graph_canvas.back_requested.connect(self._on_graph_back)             # DELETE
w.graph_canvas.node_clicked.connect(self._on_graph_node_clicked)       # DELETE
w.brain_view_action.triggered.connect(self._on_graph_view_requested)   # DELETE
```

#### Method calls to remove (inside `_apply_initial_ui_state`)
```python
self._init_vault_index(vault)   # DELETE this call
```

#### Method calls to remove (inside `_on_settings`)
```python
self._init_vault_index(vault)   # DELETE this call
```

#### Code block to remove (inside `_launch_notes_worker`)
Remove the entire `existing_fps` block and the `fingerprint_engine` kwarg passed to
`NotesWorker`. After removal the constructor call becomes:
```python
self._notes_worker = NotesWorker(
    transcript=transcript,
    course_name=course.get("name", "Unknown"),
    lecture_num=self._lecture_num,
    date=today,
    api_key=api_key,
    model_id=self._config.get("gemma_model", "gemma-4-31b-it"),
    temperature=float(self._config.get("temperature", 0.2)),
    max_tokens=int(self._config.get("max_tokens", 8192)),
    custom_instruction=custom_instruction,
    is_continuation=is_continuation,
    existing_notes_tail=notes_tail,
    # fingerprint_engine and existing_fingerprints removed
)
```
`_notes_fingerprint` tracking and `inject_frontmatter(fingerprint=...)` in `_on_save` can
remain — when `fingerprint_engine` is not passed, `notes_worker.fingerprint_str` stays `""`
and `inject_frontmatter(fingerprint=None)` simply omits the frontmatter field.

#### Entire methods to delete
All of these methods reference deleted types or are exclusively used by the graph/index
pipeline. None of them are called from outside the graph/index code paths.

| Method | Why |
|--------|-----|
| `_on_graph_view_requested` | Shows graph canvas, calls `_build_graph_data`, references `self._window.graph_canvas` |
| `_on_graph_back` | Calls `self._window.hide_graph_view()` |
| `_on_graph_node_clicked` | Calls `self._window.hide_graph_view()` |
| `_build_graph_data` | Walks disk + queries `VaultIndex`; returns raw node/edge lists for graph |
| `_init_vault_index` | Creates `VaultIndex`, `EmbeddingEngine`, `FingerprintEngine`, `IndexWorker`; also references `sidebar._vault_watcher` which has never existed (sidebar stores it as `_watcher`) |
| `_prune_missing_notes` | Walks VaultIndex rows to remove stale entries |
| `_scan_and_enqueue_vault` | Walks vault dir and marks all `.md` files dirty=1 in VaultIndex |
| `_start_index_worker` | Creates and starts `IndexWorker` |
| `_on_reindex_ready` | Callback from `VaultWatcher.reindex_ready` signal |
| `_on_index_progress` | Shows "Indexing vault… N/M" in status bar |
| `_on_index_finished` | Clears indexing status |
| `_on_index_error` | Logs IndexWorker error |

**Safety note:** `sidebar._vault_watcher` (referenced inside `_init_vault_index`) has always
been a dead reference. The sidebar stores its `VaultWatcher` as `self._watcher`, not
`self._vault_watcher`. This means the `VaultIndex ↔ VaultWatcher` integration was never
wired up and removing this code changes no currently-working behaviour.

### 10.4 `echos/ui/main_window.py` — Required Changes

#### Import to remove
```python
from echos.ui.graph_canvas import GraphCanvasWidget   # DELETE
```

#### Code to remove in `__init__`
```python
self.graph_canvas = GraphCanvasWidget()   # DELETE

# In the content stack block — DELETE both lines below:
self._content_stack = QStackedWidget()
self._content_stack.addWidget(self.tab_manager.tab_widget)  # index 0
self._content_stack.addWidget(self.graph_canvas)             # index 1
```
Replace the `QStackedWidget` with direct placement of `self.tab_manager.tab_widget` inside the
top splitter:
```python
# REPLACE the QStackedWidget block with:
top_splitter.addWidget(self.tab_manager.tab_widget)
```
Update the top-splitter `setSizes` call to match (was `[248, 972]`).

#### Methods to remove
```python
def show_graph_view(self) -> None: ...   # DELETE
def hide_graph_view(self) -> None: ...   # DELETE
```

#### Menu item to remove (inside `_build_menu`)
```python
self.brain_view_action = QAction("Brain View", self)
self.brain_view_action.setShortcut(QKeySequence("Ctrl+G"))
view_menu.addAction(self.brain_view_action)
```
Remove all three lines. The `view_menu` can remain for future use.

#### `QStackedWidget` import
Remove `QStackedWidget` from the `from PyQt6.QtWidgets import (...)` block if it is no longer
used elsewhere in this file (it is only used for `_content_stack`).

### 10.5 `echos/ui/sidebar.py` — Required Changes

#### Signal declaration to remove
```python
graph_view_requested  = pyqtSignal()   # DELETE
```

#### Vault header button to remove (inside `_build_ui`)
Remove the entire `vault_icon_btn` block (creation, styling, connection, and the
`vhr.addWidget(vault_icon_btn, ...)` line). The vault header row becomes just the name
label + path label, e.g.:
```python
vhr.addWidget(self._vault_name_lbl, 1)
vhr.addWidget(self._vault_path_lbl)
```

### 10.6 Files That Require No Changes

| File | Status |
|------|--------|
| `echos/core/vault_watcher.py` | `VaultWatcher` guards all `vault_index` calls with `if self._vault_index is not None`. The `reindex_ready` signal remains declared but will never fire a connected slot after `app.py` is cleaned. Zero risk. |
| `echos/core/fingerprint.py` | No imports of deleted modules. Becomes dead code after `app.py` stops instantiating `FingerprintEngine`, but causes no import or runtime errors. |
| `echos/core/notes_worker.py` | `NotesWorker.run()` line 186: `if self._fingerprint_engine is not None:` — fingerprint generation is already guarded. Passing `fingerprint_engine=None` (or omitting it) silently skips fingerprint generation and leaves `fingerprint_str = ""`. Confirmed safe. |
| `echos/utils/frontmatter.py` | `inject_frontmatter(fingerprint=None)` simply omits the frontmatter field. No change needed. |
| All other UI files | Unaffected. |

### 10.7 Data Note

Existing vaults already have a `.echoes/vault.index.db` SQLite file created by the old
`VaultIndex` constructor. This file is inert after Phase 26 (nothing reads or writes it).
It can be left in place or the user can delete `.echoes/` manually. The app will not attempt
to create or read it.

### 10.8 Verification Checklist

After completing all code changes, verify manually:

1. **Cold launch** — app starts without `sentence-transformers` installed; no `ImportError`.
2. **Vault tree** — set a vault path; tree populates, folder clicks work, note clicks open tabs.
3. **VaultWatcher** — create/rename a file in the vault externally; tree refreshes within ~1s.
4. **Recording → Notes** — record 30 s, stop, generate notes; notes stream in correctly.
5. **Save** — save generated notes; file appears in vault; frontmatter present, no `fingerprint:` field.
6. **Brain View UI** — confirm vault header has no icon button; View menu has no "Brain View" item; `Ctrl+G` does nothing.
7. **Multi-tab editor** — click a vault `.md` file; opens in new editor tab; edit and save work.

---

## 11. Phase 27 — Full-Featured Sidebar CRUD

### 11.1 Drag-and-Drop File Moving

`_VaultTree` (the `QTreeWidget` subclass in `sidebar.py`) gains full drag-and-drop:

- Call `setDragEnabled(True)`, `setAcceptDrops(True)`, `setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)`.
- Override `dropEvent`: before calling `super().dropEvent()`, intercept the event to extract the **source path** (from the dragged item's `UserRole` data) and **target folder path** (from the item under the drop point). Call `shutil.move(src, target_dir / src.name)`. If `shutil.move` succeeds, suppress the default Qt tree reorder (call `event.accept()` without `super()`) and let `VaultWatcher.tree_changed` trigger the UI refresh instead. On error, show a `QMessageBox.warning`.
- Guard against dropping a folder onto itself or one of its own descendants (would create a recursive loop).
- Guard against dropping to the same parent (no-op).

### 11.2 Right-Click Context Menu

`_VaultTree` handles `customContextMenuRequested` (set `setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)`):

Context menu items vary by target:

| Target | Actions |
|--------|---------|
| Folder | New File, New Folder, Rename, Delete Folder |
| File | Rename, Delete File, Reveal in Finder |
| Empty space / root | New File at root, New Folder at root |

- **New File**: `QInputDialog.getText` for the filename (auto-appends `.md` if omitted). Creates an empty file with `Path.touch()`. VaultWatcher refreshes.
- **New Folder**: `QInputDialog.getText` for the folder name. `Path.mkdir(parents=True, exist_ok=True)`. VaultWatcher refreshes.
- **Rename**: triggers inline rename (see §11.3).
- **Delete File**: `QMessageBox.question` confirm, then `Path.unlink()`. Emit `file_deleted(str)` signal so open editor tabs for that file can be closed.
- **Delete Folder**: `QMessageBox.question` confirm with folder name + "all contents". `shutil.rmtree()`. Emit `file_deleted(str)` for each `.md` file within.
- **Reveal in Finder** (macOS): `subprocess.run(["open", "-R", str(path)])`.

### 11.3 Inline Rename

When Rename is triggered (context menu or `F2` key press on a selected item):

- Mark the item editable: `item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)`.
- Call `self.editItem(item, 0)` to open the inline editor.
- Connect `itemChanged` to `_on_item_renamed(item, old_name)`: on change, call `shutil.move(old_path, old_path.parent / new_name)`. If the move fails, revert the item text and show a warning.
- After editing, remove the `ItemIsEditable` flag to prevent accidental double-clicks from triggering rename.
- If a file is renamed that has an open editor tab, emit `file_renamed(old_path: str, new_path: str)` via `SidebarWidget` so `TabManager` can update its `_path_to_index` map and tab label.

### 11.4 New Signals on `SidebarWidget`

```python
file_deleted = pyqtSignal(str)               # absolute path removed from disk
file_renamed = pyqtSignal(str, str)          # (old_abs_path, new_abs_path)
```

`AppController._connect_signals` wires these:
- `file_deleted`: call `tab_manager.close_tabs_for_path(path)` (close any tab whose file_path matches).
- `file_renamed`: call `tab_manager.rename_tab_path(old, new)` (update path map and tab label).

### 11.5 `TabManager` extensions required

```python
def close_tabs_for_path(self, path: str) -> None:
    """Close any tab whose EditorTab.file_path() == path, without unsaved-changes prompt."""

def rename_tab_path(self, old_path: str, new_path: str) -> None:
    """Update path→index map and tab label if old_path is open."""
```

---

## 12. Phase 28 — Split Views & Tear-off Tabs

### 12.1 Architecture

Introduce a new widget `SplitTabArea` (`echos/ui/split_tab_area.py`) that owns a `QSplitter` containing one or more `TabManager` panel widgets. `MainWindow` replaces the direct `TabManager.tab_widget` reference with `SplitTabArea`.

```
MainWindow
  └─ top_splitter
       ├─ SidebarWidget
       └─ SplitTabArea (QWidget)
            └─ _splitter (QSplitter)
                 ├─ TabManager A  ← primary (owns Echoes tab, index 0)
                 └─ TabManager B  ← spawned by split action (no Echoes tab)
```

`MainWindow.tab_manager` becomes a property returning `split_tab_area.primary_manager` (the original `TabManager` that holds the Echoes tab). `app.py` calls `self._window.tab_manager.open_file(...)` — unchanged.

The active manager (the one most recently focused) is tracked separately for routing `open_file` calls from the command palette and file double-clicks.

### 12.2 Split Right / Split Down

`EchosTabBar` gains a right-click context menu (override `mousePressEvent` to detect `Qt.RightButton`):

| Action | Behaviour |
|--------|-----------|
| Split Right | `split_tab_area.split(Qt.Orientation.Horizontal)` |
| Split Down | `split_tab_area.split(Qt.Orientation.Vertical)` |
| Close Pane | `split_tab_area.close_pane(manager)` (disallowed for primary) |

`split_tab_area.split(orientation)`:
1. Create a new `TabManager(None)` — no Echoes tab (pass `None` as `echoes_widget`).
2. `TabManager.__init__` skips adding tab 0 when `echoes_widget is None`.
3. Insert new `TabManager.tab_widget` into `_splitter` at the next index.
4. Set focus to the new panel.

`split_tab_area.close_pane(manager)`:
1. Close all file tabs inside the manager (with unsaved-changes prompts).
2. Remove its `tab_widget` from `_splitter`.
3. If only the primary manager remains, destroy the splitter and revert to single layout.

### 12.3 Tear-off Tabs

`EchosTabBar` overrides `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent` to implement drag detection:

1. `mousePressEvent`: record start position `_drag_start_pos` and the tab index under the cursor.
2. `mouseMoveEvent`: when drag distance > 40 px **and** the cursor is **outside** the tab bar rect, emit `tearoff_requested(index: int)` signal. Reset drag state.
3. `SplitTabArea` handles `tearoff_requested(index)`:
   - Extract the `EditorTab` widget at that index.
   - Remove the tab from the `TabManager` (call `close_tab` without unsaved-changes handling — the EditorTab is being transferred, not closed).
   - Create `TearOffWindow(editor_tab, file_path, parent=None)`.
   - Show the `TearOffWindow`.
4. `TearOffWindow(QMainWindow)`:
   - Warm-parchment styled frameless window (800×600 default size).
   - Contains the detached `EditorTab` as central widget.
   - Toolbar row with: file name label + "Dock Back" button.
   - **Dock Back**: clicking "Dock Back" calls `split_tab_area.dock_tab(editor_tab, path)`, which re-inserts the tab into the primary `TabManager` and closes the `TearOffWindow`.

### 12.4 Keyboard & Menu

- `Ctrl+\` — Split Right (new shortcut, registered in MainWindow).
- `Ctrl+Shift+\` — Close current pane (if not primary).
- Right-click on tab bar shows context menu with Split Right, Split Down, Close Pane.

---

## 13. Phase 29 — Seamless Image Pasting

### 13.1 `_MarkdownEditor` subclass

`editor_tab.py` introduces a `_MarkdownEditor(QTextEdit)` subclass used in place of the bare `QTextEdit` for the `_editor` widget:

```python
class _MarkdownEditor(QTextEdit):
    def __init__(self, vault_root: Path | None = None, parent=None): ...
    def set_vault_root(self, vault_root: Path) -> None: ...
    def keyPressEvent(self, event) -> None: ...  # intercepts Ctrl/Cmd+V for images
    def dropEvent(self, event) -> None: ...      # intercepts dropped image files
```

### 13.2 Image Detection and Save

When `keyPressEvent` receives `Ctrl+V` (or `Meta+V` on macOS), check `QApplication.clipboard().mimeData()`:
- If `mimeData.hasImage()` → extract via `mimeData.imageData()` as a `QImage`.
- If `mimeData.hasUrls()` → check if any URL points to an image file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`).

Image save path: `{vault_root}/.assets/` if `vault_root` is set, else `{file_dir}/.assets/`. Create the directory with `Path.mkdir(exist_ok=True)`.

Filename: `pasted_image_{YYYYMMDD_HHMMSS}.png`.

Save: `QImage.save(str(save_path), "PNG")` for clipboard images; `shutil.copy` for URL-sourced images.

Insert at cursor: `self.insertPlainText(f"![image](.assets/{filename})")`.

On error: fall through to default `QTextEdit.keyPressEvent(event)` (normal text paste).

### 13.3 Vault Root Plumbing

`EditorTab.load_file(path: str, vault_root: str = "")`:
- Store `vault_root` and call `self._editor.set_vault_root(Path(vault_root))` if non-empty.

`TabManager.open_file(path: str, vault_root: str = "")`:
- Pass `vault_root` through to `EditorTab.load_file`.

`AppController._on_note_selected(path_str: str)`:
- Call `self._window.tab_manager.open_file(path_str, vault_root=self._config.get("vault_path", ""))`.

---

## 14. Phase 30 — Unified Command Palette & Quick Peek

### 14.1 Command Palette (`echos/ui/command_palette.py`)

`CommandPalette(QDialog)`:
- `Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog` — no title bar.
- Background: `PANEL_BG` at 95% opacity (use `setWindowOpacity(0.97)`).
- `BORDER_SOFT` border + 8px radius via `setStyleSheet`.
- Size: 520×360, centered over parent window.
- Layout: search `QLineEdit` (40px height, `PANEL_BG`, `ACCENT` focus border) + `QListWidget` (fills rest).
- Closes on `Escape` or clicking outside (install event filter or override `focusOutEvent`).

**Results model** — two categories shown interleaved, type-annotated:

| Prefix | Category |
|--------|---------|
| (none) | Vault files matching fuzzy query |
| `>` prefix | Commands matching fuzzy query |

File results: walk vault directory tree (all `.md` files). Filter by fuzzy match against relative path. Show filename (bold) + relative path (muted, smaller).

Command results (built-in registry):
- `> New Recording` → `AppController._on_new_recording()`
- `> Settings` → `AppController._on_settings()`
- `> Save Note` → `AppController._on_save()`
- `> Toggle Transcript` → hide/show transcript panel
- `> Toggle Notes` → hide/show notes panel

**Keyboard behaviour**: ↑/↓ navigate list; Enter activates; Escape closes.

**Fuzzy matching algorithm**: check that all characters of the query appear in the result string in order (subsequence match). Score = 1.0 if consecutive match, 0.5 if scattered; sort by score descending.

### 14.2 Shortcut

`Ctrl+Shift+P` opens the command palette (note: `Ctrl+P` = ⌘P on macOS is reserved for Pause Recording).

In `MainWindow._build_menu`: add `self.command_palette_action = QAction("Command Palette", self)` with shortcut `Ctrl+Shift+P` to the View menu.

In `AppController._connect_signals`: `w.command_palette_action.triggered.connect(self._on_command_palette)`.

`AppController._on_command_palette`: instantiate `CommandPalette(vault_path, command_registry, parent=self._window)` and call `.exec()`.

### 14.3 Quick Peek — Hover Preview for Wikilinks

`_MarkdownEditor` adds hover tracking:

- Set `setMouseTracking(True)`.
- Override `mouseMoveEvent`: find the text cursor at `event.pos()` using `cursorForPosition`. Extract the line text. Run `re.search(r'\[\[([^\]]+)\]\]', line)` to find wikilinks. Determine if the cursor column falls inside a `[[...]]` span.
- If a wikilink is found: start `_hover_timer` (QTimer, 500 ms one-shot) with the target name stored.
- If cursor moves off the wikilink: stop `_hover_timer` and hide any visible preview.
- On `_hover_timer` timeout: resolve the wikilink to a file path by scanning vault (stem match, case-insensitive). If found, create/show `_WikilinkPreview`.

`_WikilinkPreview(QWidget)`:
- `Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint`.
- Background: `PANEL_BG`, border `BORDER_SOFT`, 6px radius, 12px padding.
- Size: 360×200. Positioned 16px below cursor (screen coordinates).
- Content: `QTextBrowser` rendering the first 15 lines of the target file as HTML (using `_md_to_html`).
- Header: filename label in bold + `TEXT_FAINT` muted path.
- Auto-hides on `leaveEvent` or when a new mouse position is not over the preview widget.
- Vault root required to resolve wikilinks — passed from `EditorTab` via `set_vault_root`.
