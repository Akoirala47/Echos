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
