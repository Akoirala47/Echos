# Scout — Project Specification

> A native macOS lecture note-taking app that transcribes audio locally with NVIDIA Canary-Qwen 2.5B and structures notes via Gemma 4 31B, saving directly into an Obsidian vault. Distributed as a signed `.dmg`.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Architecture](#3-architecture)
4. [Feature Specification](#4-feature-specification)
5. [UI/UX Design Spec](#5-uiux-design-spec)
6. [Module Breakdown](#6-module-breakdown)
7. [Local Model Handling (Canary-Qwen)](#7-local-model-handling-canary-qwen)
8. [Gemma 4 31B Integration](#8-gemma-4-31b-integration)
9. [Obsidian Integration](#9-obsidian-integration)
10. [App Bundling — `.app` + `.dmg](#10-app-bundling--app--dmg)`
11. [GitHub Repository Structure](#11-github-repository-structure)
12. [First-Launch Experience](#12-first-launch-experience)
13. [Settings — Full Spec](#13-settings--full-spec)
14. [Data & Config Storage](#14-data--config-storage)
15. [Error Handling Strategy](#15-error-handling-strategy)

---

## 1. Project Overview

### What it does

Scout is a macOS menu-bar and windowed app for students. The user selects a course, hits Record, and Scout:

1. Captures microphone audio continuously
2. Transcribes it in real time, locally, using NVIDIA Canary-Qwen 2.5B (running on Apple Silicon via MPS)
3. After the user stops recording, sends the full transcript to Gemma 4 31B via Google AI API
4. Displays structured markdown notes with headings, bullet points, code blocks, and definitions
5. Saves the note as a `.md` file into the correct folder inside the user's Obsidian vault
6. Auto-increments lecture numbers based on existing files

### Non-goals (v1)

- No real-time note generation (notes are generated post-recording only)
- No sync across devices
- No Windows/Linux support
- No audio file import (mic only)

---

## 2. Tech Stack

### Decision rationale

The app needs to:

- Run a 2.5B parameter ASR model locally on Apple Silicon
- Present a polished native Mac UI
- Be distributable as a self-contained `.dmg` with no user-side Python install
- Ship on GitHub with automated builds


| Concern            | Choice                                             | Why                                                                                                  |
| ------------------ | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| UI framework       | **PyQt6**                                          | Full macOS native look, excellent Python bindings, works with py2app                                 |
| Local ML inference | **transformers + Apple MPS**                       | `nvidia/canary-qwen-2.5b` loads via HuggingFace transformers; MPS gives ~4-8x speedup over CPU on M1 |
| Google API         | **google-generativeai SDK**                        | Official SDK, handles auth and streaming                                                             |
| Audio capture      | **sounddevice**                                    | Low-latency mic access, cross-platform but Mac-first                                                 |
| App bundling       | **py2app**                                         | Produces a proper `.app` bundle with embedded Python runtime                                         |
| DMG creation       | **create-dmg** (npm)                               | Industry standard, drag-install layout, background image support                                     |
| Model download     | **huggingface_hub**                                | Handles resumable downloads, caching, progress callbacks                                             |
| Config storage     | **JSON** in `~/Library/Application Support/Scout/` | macOS convention                                                                                     |


### Python version

**Python 3.11** — best MPS support, fully compatible with all dependencies listed.

### Key dependencies

```
PyQt6>=6.6.0
transformers>=4.45.0
torch>=2.2.0              # Apple Silicon MPS backend included
torchaudio>=2.2.0
sounddevice>=0.4.6
numpy>=1.26.0
huggingface_hub>=0.24.0
google-generativeai>=0.8.0
nemo_toolkit[asr]>=2.0.0  # optional, only if using NeMo inference path
soundfile>=0.12.1
py2app>=0.28.0            # build only
```

> **Note on torch:** The `torch` package from `pip` includes MPS support for Apple Silicon. No special build required. Model will automatically use `mps` device on M-series Macs and fall back to `cpu` on Intel.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Scout.app                                │
│                                                                 │
│  ┌──────────────┐     ┌────────────────────────────────────┐   │
│  │   PyQt6 UI   │◄───►│          App Controller            │   │
│  │  (main thread│     │   (orchestrates all workers)       │   │
│  └──────────────┘     └──────────────┬─────────────────────┘   │
│                                      │                          │
│              ┌───────────────────────┼───────────────┐          │
│              ▼                       ▼               ▼          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐   │
│  │  Audio Worker   │  │  Notes Worker    │  │  Obsidian   │   │
│  │  (QThread)      │  │  (QThread)       │  │  Manager    │   │
│  │                 │  │                  │  │             │   │
│  │  sounddevice    │  │  google-         │  │  Path I/O   │   │
│  │  → chunk buffer │  │  generativeai    │  │  Markdown   │   │
│  │  → Canary-Qwen  │  │  Gemma 4 31B     │  │  write      │   │
│  │  (local, MPS)   │  │  (Google API)    │  └─────────────┘   │
│  └─────────────────┘  └──────────────────┘                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Model Manager                           │  │
│  │  - Checks if Canary-Qwen weights cached locally          │  │
│  │  - Downloads via huggingface_hub if missing              │  │
│  │  - Shows progress UI                                     │  │
│  │  - Loads model once at startup, holds in memory          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Config Manager                          │  │
│  │  ~/Library/Application Support/Scout/config.json         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Threading model


| Thread                          | Responsibility                                 |
| ------------------------------- | ---------------------------------------------- |
| Main (Qt)                       | UI rendering, user interaction, signal routing |
| `AudioWorker` (QThread)         | Mic capture + chunked Canary-Qwen inference    |
| `NotesWorker` (QThread)         | Google API call for Gemma 4 31B                |
| `ModelDownloadWorker` (QThread) | First-launch model download with progress      |


All inter-thread communication is via Qt signals/slots. No shared mutable state.

---

## 4. Feature Specification

### 4.1 Course Management

- **Add course**: name + vault subfolder (auto-filled from name, editable)
- **Delete course**: with confirmation dialog
- **Reorder courses**: drag-and-drop in sidebar
- **Course color**: 8 preset accent colors, user selects
- **Auto-detect lecture number**: scans course folder for `Lecture-NN.md` files on selection, sets next number
- **Manual lecture override**: user can change lecture number before recording

### 4.2 Recording

- **Start/Stop button**: large, prominent, with keyboard shortcut `⌘R`
- **Live waveform**: animated bar visualization reacts to actual audio levels (not random)
- **Elapsed timer**: mm:ss display
- **Live transcript panel**: updates every ~5 seconds as Canary-Qwen processes chunks
- **Pause/Resume**: ⌘P pauses audio capture without ending the session
- **Recording indicator**: red dot in macOS Dock while recording is active
- **Prevent sleep**: `NSProcessInfo` power assertion keeps Mac awake during recording

### 4.3 Transcription (Canary-Qwen 2.5B — Local)

- Model loaded once at app launch (or after download), stays in memory
- Audio chunked into 6-second segments with 0.5s overlap to avoid sentence cuts
- Each chunk processed synchronously on the `AudioWorker` thread
- Result appended to live transcript with a subtle fade-in animation
- Transcript is fully editable by the user at any time
- User can highlight and delete sections before generating notes

### 4.4 Notes Generation (Gemma 4 31B — Google API)

- Triggered manually via "Generate Notes" button after recording stops
- Full transcript sent with structured system prompt
- Response streamed and displayed incrementally (streaming API)
- Notes rendered in a markdown-aware preview pane (rendered HTML, not raw markdown)
- Toggle between rendered preview and raw markdown edit view
- "Regenerate" option with optional custom instruction ("focus more on the algorithm proofs")
- Notes are fully editable before saving

### 4.5 Saving to Obsidian

- One-click save: "Save to Obsidian" writes to `{vault}/{course_folder}/Lecture-{NN}.md`
- Filename format: `Lecture-01.md`, `Lecture-02.md`, etc.
- Front matter injected automatically:
  ```yaml
  ---
  course: CS446
  lecture: 26
  date: 2026-04-24
  tags: [cs446, lecture]
  ---
  ```
- Creates folder if it doesn't exist
- Asks before overwriting if file already exists
- "Open in Obsidian" button after save (calls `obsidian://open?vault=...&file=...`)

### 4.6 Settings (in-app, no config files)

See full spec in [Section 13](#13-settings--full-spec).

### 4.7 Menu Bar Integration

- App lives in the Dock and has a standard menu bar
- `Scout` menu: About, Settings (`⌘,`), Quit
- `File` menu: New Recording (`⌘N`), Save Note (`⌘S`), Export Transcript
- `View` menu: Toggle Transcript/Notes panels, Toggle Markdown Preview
- `Help` menu: Model Status, Open Log File

### 4.8 Export

- Export raw transcript as `.txt`
- Export structured notes as `.md`
- Copy notes to clipboard

---

## 5. UI/UX Design Spec

### 5.1 Window layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ●  ●  ●          Scout — CS446                         ⊡  ─  ✕  │
├──────────────────────────────────────────────────────────────────┤
│           │                                                       │
│  COURSES  │   CS446                             Lecture 26       │
│  ───────  │  ─────────────────────────────────────────────────  │
│  CS446 ●  │                                                       │
│  CS350    │   [  ● Start Recording  ]  ▂▄▇▄▂▄  0:00             │
│  MATH301  │                                                       │
│  CS488    │   ╔══════════════════════╦═══════════════════════╗   │
│           │   ║  LIVE TRANSCRIPT     ║  STRUCTURED NOTES     ║   │
│  ────     │   ║──────────────────────║───────────────────────║   │
│  + Course │   ║                      ║                       ║   │
│           │   ║  (transcript text    ║  (rendered markdown   ║   │
│           │   ║   appears here       ║   notes appear here   ║   │
│           │   ║   in real time)      ║   after generation)   ║   │
│  ────     │   ║                      ║                       ║   │
│  ⚙ Settings   ╚══════════════════════╩═══════════════════════╝   │
├──────────────────────────────────────────────────────────────────┤
│  ● Ready · CS446 · ~/obsidian/great-days      [Save to Obsidian] │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Visual design

- **Color scheme**: Light mode primary, full dark mode support via Qt palette
- **Sidebar**: `#F8F8F6` background, 186px fixed width, resizable via drag
- **Accent color**: follows macOS system accent color
- **Typography**: `.AppleSystemUIFont` (San Francisco) throughout — no custom fonts
- **Animations**: waveform bars animate to real audio RMS levels, not random
- **Record button states**:
  - Default: white background, dark border, `● Start Recording`
  - Recording: `#FFF2F1` background, red border, `■ Stop Recording`, pulsing dot
  - Paused: `#FFF8E7` background, amber border, `▶ Resume Recording`
- **Window minimum size**: 820 × 560px
- **Vibrancy**: sidebar uses `QGraphicsBlurEffect` or native NSVisualEffectView where possible

### 5.3 Notes panel — markdown rendering

Use `QTextBrowser` with a custom CSS stylesheet to render markdown as HTML:

- `# H1` → large bold heading
- `## H2` → section heading with subtle left border
- Code blocks → monospace, `#F5F5F2` background, 1px border
- Bold → `font-weight: 600`
- Bullet points → proper list rendering
- Toggle button in panel header switches between rendered view and raw `QTextEdit`

### 5.4 Onboarding / First Launch

See [Section 12](#12-first-launch-experience).

---

## 6. Module Breakdown

```
scout/
├── main.py                    # Entry point, QApplication init
├── app.py                     # AppController: wires all modules together
│
├── ui/
│   ├── main_window.py         # QMainWindow shell + layout
│   ├── sidebar.py             # Course list, add/delete, drag reorder
│   ├── record_bar.py          # Record button, waveform, timer
│   ├── transcript_panel.py    # Live transcript QTextEdit + toolbar
│   ├── notes_panel.py         # Notes QTextBrowser (rendered) + raw toggle
│   ├── status_bar.py          # Status dot, vault path, Save button
│   ├── settings_window.py     # Full settings QDialog
│   ├── onboarding.py          # First-launch wizard (model download + setup)
│   └── widgets/
│       ├── waveform.py        # Custom QPainter waveform widget
│       ├── course_item.py     # Custom QListWidgetItem with color dot
│       └── model_progress.py  # Download progress bar widget
│
├── core/
│   ├── audio_worker.py        # QThread: mic capture + Canary-Qwen inference
│   ├── notes_worker.py        # QThread: Gemma 4 31B via Google API (streaming)
│   ├── model_manager.py       # Canary-Qwen download, load, MPS device setup
│   └── obsidian_manager.py    # Vault path ops, file write, lecture numbering
│
├── config/
│   ├── config_manager.py      # Read/write ~/Library/Application Support/Scout/
│   └── defaults.py            # Default config values
│
├── utils/
│   ├── markdown.py            # Transcript → Gemma prompt builder
│   ├── audio_utils.py         # RMS level, chunk splitter, overlap logic
│   └── frontmatter.py        # YAML front matter injector for saved notes
│
├── assets/
│   ├── icon.icns              # App icon (required for DMG)
│   ├── dmg_background.png     # DMG window background image
│   └── icon_512.png           # Source icon
│
├── build/
│   ├── setup.py               # py2app configuration
│   ├── build.sh               # Full build script: py2app → DMG
│   └── entitlements.plist     # macOS sandbox entitlements for signing
│
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Dev + build dependencies
└── README.md
```

---

## 7. Local Model Handling (Canary-Qwen)

### Model details


| Property          | Value                                             |
| ----------------- | ------------------------------------------------- |
| Model ID          | `nvidia/canary-qwen-2.5b`                         |
| Type              | ASR (Automatic Speech Recognition)                |
| Parameters        | 2.5 billion                                       |
| Download size     | ~5 GB                                             |
| Cache location    | `~/.cache/huggingface/hub/` (HuggingFace default) |
| Device            | `mps` on Apple Silicon, `cpu` fallback on Intel   |
| Inference library | `transformers` (HuggingFace)                      |


### Loading strategy

```python
# core/model_manager.py

from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
import torch

class ModelManager:
    MODEL_ID = "nvidia/canary-qwen-2.5b"

    def __init__(self):
        self.model = None
        self.processor = None
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"

    def is_cached(self) -> bool:
        """Check if model weights exist locally without downloading."""
        from huggingface_hub import try_to_load_from_cache
        result = try_to_load_from_cache(self.MODEL_ID, "config.json")
        return result is not None

    def download(self, progress_callback):
        """Download model with progress reporting. Called from ModelDownloadWorker."""
        from huggingface_hub import snapshot_download
        snapshot_download(
            self.MODEL_ID,
            local_files_only=False,
            # huggingface_hub does not expose per-file progress natively
            # wrap with tqdm or poll cache dir size vs expected size
        )

    def load(self):
        """Load model into memory. Called once at app startup."""
        self.processor = AutoProcessor.from_pretrained(self.MODEL_ID)
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.MODEL_ID,
            torch_dtype=torch.float16 if self.device == "mps" else torch.float32,
        ).to(self.device)
        self.model.eval()

    def transcribe(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a numpy float32 audio chunk. Returns text string."""
        inputs = self.processor(
            audio_chunk,
            sampling_rate=sample_rate,
            return_tensors="pt"
        ).to(self.device)
        with torch.no_grad():
            output_ids = self.model.generate(**inputs)
        return self.processor.batch_decode(output_ids, skip_special_tokens=True)[0]
```

> **Important:** `AutoModelForSpeechSeq2Seq` may not be the correct class for Canary-Qwen — verify against the model card on HuggingFace at `https://huggingface.co/nvidia/canary-qwen-2.5b`. The model may require NeMo's `EncDecMultiTaskModel`. If NeMo is required, the load path changes but the chunking and MPS logic stays the same.

### Audio chunking

```
┌──────────────────────────────────────────────────────────┐
│  Continuous mic stream (16kHz, mono, float32)            │
│                                                          │
│  [  chunk 1 (6s)  |0.5s][  chunk 2 (6s)  |0.5s] ...    │
│                    └────┘                                │
│                  overlap prevents word cuts at edges     │
└──────────────────────────────────────────────────────────┘
```

- Chunk size: 6 seconds (96,000 samples at 16kHz)
- Overlap: 0.5 seconds on both sides
- Deduplicate overlapping transcribed words before appending
- Process chunks serially (not parallel) to avoid memory spikes on M1 base (16GB)

### Memory budget on M1 Pro 16GB


| Item                      | VRAM/RAM |
| ------------------------- | -------- |
| macOS + Safari/apps       | ~6 GB    |
| Canary-Qwen 2.5B (fp16)   | ~5 GB    |
| PyQt6 + Python runtime    | ~300 MB  |
| Available for rest of app | ~4.7 GB  |


16GB is sufficient. Model stays loaded the entire app session — do not unload between recordings.

---

## 8. Gemma 4 31B Integration

### API setup

```python
# core/notes_worker.py

import google.generativeai as genai

class NotesWorker(QThread):
    chunk_ready = pyqtSignal(str)   # streaming chunk
    done        = pyqtSignal(str)   # full completed notes
    error       = pyqtSignal(str)

    def run(self):
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel("gemma-4-31b-it")

        response = model.generate_content(
            self._build_prompt(),
            stream=True,           # stream for incremental display
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,   # low temp for factual notes
                max_output_tokens=8192,
            )
        )
        full = ""
        for chunk in response:
            text = chunk.text
            full += text
            self.chunk_ready.emit(text)   # update notes panel live
        self.done.emit(full)
```

### Prompt structure

```
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
- Output only the markdown. No preamble, no "Here are your notes:"

Transcript:
{transcript}
```

### Regenerate with custom instruction

When user hits "Regenerate", show a small text input:

> "Any specific focus for regeneration? (optional)"

Append to prompt: `\n\nAdditional instruction: {user_instruction}`

---

## 9. Obsidian Integration

### Vault operations

```python
# core/obsidian_manager.py

class ObsidianManager:

    def next_lecture_num(self, vault: Path, folder: str) -> int:
        """Scan folder for Lecture-NN.md, return max N + 1."""

    def save_note(self, vault: Path, folder: str, num: int,
                  content: str, course: str, date: str) -> Path:
        """Write note with YAML front matter. Creates folder if needed."""

    def open_in_obsidian(self, vault_name: str, file_path: str):
        """Call obsidian:// URI scheme to open the file."""
        import subprocess
        uri = f"obsidian://open?vault={vault_name}&file={file_path}"
        subprocess.run(["open", uri])
```

### Saved file format

```markdown
---
course: CS446
lecture: 26
date: 2026-04-24
tags: [cs446, lecture, notes]
scout_version: 1.0.0
---

# CS446 · Lecture 26
*April 24, 2026*

## Dynamic Programming

...rest of notes...

## Key Takeaways

- ...
```

### Folder structure expected in vault

```
great-days/
  CS446/
    Lecture-01.md
    Lecture-02.md
    ...
  CS350/
    Lecture-01.md
```

- Scout creates the course subfolder on first save if missing
- Scout does NOT create or manage the vault itself — user must have Obsidian installed

---

## 10. App Bundling — `.app` + `.dmg`

### py2app configuration

```python
# build/setup.py

from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/icon.icns",
    "plist": {
        "CFBundleName": "Scout",
        "CFBundleDisplayName": "Scout",
        "CFBundleIdentifier": "com.yourname.scout",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSMicrophoneUsageDescription":
            "Scout needs microphone access to transcribe your lectures.",
        "NSDocumentsFolderUsageDescription":
            "Scout needs access to your Documents folder to save notes to Obsidian.",
        "LSMinimumSystemVersion": "13.0",   # macOS Ventura+
        "NSHighResolutionCapable": True,
    },
    "packages": [
        "PyQt6", "torch", "transformers", "sounddevice",
        "numpy", "google.generativeai", "huggingface_hub",
    ],
    "excludes": ["tkinter", "matplotlib", "scipy"],
    "strip": False,
    "optimize": 0,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
```

### Build script

```bash
# build/build.sh

#!/bin/bash
set -e

echo "=== Cleaning previous build ==="
rm -rf build/ dist/

echo "=== Building .app with py2app ==="
python build/setup.py py2app

echo "=== Creating .dmg ==="
npx create-dmg \
  --volname "Scout" \
  --background "assets/dmg_background.png" \
  --window-size 540 380 \
  --icon-size 100 \
  --icon "Scout.app" 130 190 \
  --app-drop-link 410 190 \
  "dist/Scout-1.0.0.dmg" \
  "dist/Scout.app"

echo "=== Done: dist/Scout-1.0.0.dmg ==="
```

### macOS code signing (for distribution)

```bash
# Sign the app (requires Apple Developer account, $99/yr)
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  --entitlements build/entitlements.plist \
  dist/Scout.app

# Notarize (Apple scans for malware, required for Gatekeeper)
xcrun notarytool submit dist/Scout-1.0.0.dmg \
  --apple-id "your@email.com" \
  --password "@keychain:AC_PASSWORD" \
  --team-id "TEAMID" \
  --wait

# Staple notarization ticket to DMG
xcrun stapler staple dist/Scout-1.0.0.dmg
```

```xml
<!-- build/entitlements.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.device.audio-input</key>  <true/>
  <key>com.apple.security.files.user-selected.read-write</key>  <true/>
  <key>com.apple.security.network.client</key>  <true/>
</dict>
</plist>
```

> **Without a Developer account**: Users can still install by right-clicking the `.app` and selecting "Open" the first time. Document this in the README. Code signing is only required for automatic Gatekeeper bypass.

### DMG size estimate


| Component                | Size                                           |
| ------------------------ | ---------------------------------------------- |
| Python runtime (bundled) | ~80 MB                                         |
| PyQt6 + Qt frameworks    | ~120 MB                                        |
| torch (MPS, no CUDA)     | ~320 MB                                        |
| transformers             | ~40 MB                                         |
| Other dependencies       | ~60 MB                                         |
| App code                 | ~1 MB                                          |
| **Total DMG**            | **~620 MB**                                    |
| Canary-Qwen weights      | ~5 GB (downloaded on first launch, NOT in DMG) |


---

## 11. GitHub Repository Structure

```
scout/
├── .github/
│   └── workflows/
│       └── build.yml          # GitHub Actions: build DMG on push to main
│
├── assets/
│   ├── icon.icns
│   ├── icon_512.png
│   └── dmg_background.png
│
├── build/
│   ├── setup.py
│   ├── build.sh
│   └── entitlements.plist
│
├── scout/                     # Python package (all source)
│   ├── main.py
│   ├── app.py
│   ├── ui/
│   ├── core/
│   ├── config/
│   └── utils/
│
├── .gitignore
├── LICENSE                    # MIT recommended
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

### GitHub Actions — auto-build DMG

```yaml
# .github/workflows/build.yml

name: Build DMG

on:
  push:
    tags: ["v*"]              # trigger on version tags e.g. v1.0.0

jobs:
  build:
    runs-on: macos-14         # Apple Silicon runner (M1)
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Build DMG
        run: chmod +x build/build.sh && ./build/build.sh

      - name: Upload DMG as release asset
        uses: softprops/action-gh-release@v2
        with:
          files: dist/Scout-*.dmg
```

### README badges

```markdown
![macOS](https://img.shields.io/badge/macOS-13%2B-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-green)
```

---

## 12. First-Launch Experience

On first launch (detected by absence of config file), show a **3-step onboarding wizard** before the main window:

### Step 1 — Welcome

```
┌─────────────────────────────────────────┐
│                                         │
│    🎓  Welcome to Scout                 │
│                                         │
│    AI-powered lecture notes for Mac.    │
│                                         │
│    We'll set up three things:           │
│    ✦  Your Obsidian vault location      │
│    ✦  Your Google AI API key            │
│    ✦  The local transcription model     │
│                                         │
│                          [ Get Started ]│
└─────────────────────────────────────────┘
```

### Step 2 — API Key + Vault

- Vault path: text field with "Browse…" button
- Google AI API key: password field with "Get a free key →" link to `aistudio.google.com/apikey`
- Validate key by making a test API call before proceeding

### Step 3 — Model Download

```
┌─────────────────────────────────────────┐
│                                         │
│  Downloading Canary-Qwen 2.5B           │
│  This happens once (~5 GB)              │
│                                         │
│  ████████████████░░░░░░░  68%           │
│  3.4 GB of 5.0 GB · 12 MB/s · 2m left  │
│                                         │
│  The model runs fully on your Mac.      │
│  Your audio never leaves your device.   │
│                                         │
│  [ Cancel ]              [ Background ] │
└─────────────────────────────────────────┘
```

- "Background" button dismisses the wizard, lets user explore the app while downloading
- Download resumes automatically if interrupted (HuggingFace Hub handles this)
- Main record button disabled until download complete, shows "Model downloading…"

---

## 13. Settings — Full Spec

Settings window (`⌘,`) with four tabs:

### Tab 1 — General


| Setting                          | Type        | Default                 |
| -------------------------------- | ----------- | ----------------------- |
| Obsidian vault path              | Path picker | (set during onboarding) |
| Auto-open in Obsidian after save | Toggle      | Off                     |
| Prevent sleep during recording   | Toggle      | On                      |
| Show waveform                    | Toggle      | On                      |
| Keyboard shortcut to start/stop  | Key capture | ⌘R                      |


### Tab 2 — API Keys


| Setting                | Type           | Notes                                       |
| ---------------------- | -------------- | ------------------------------------------- |
| Google AI API key      | Password field | Link to `aistudio.google.com/apikey`        |
| Gemma model ID         | Text field     | Default: `gemma-4-31b-it`                   |
| Test connection button | Button         | Makes a minimal test call, shows ✓ or error |


### Tab 3 — Transcription


| Setting             | Type         | Default                 | Notes                                  |
| ------------------- | ------------ | ----------------------- | -------------------------------------- |
| Transcription model | Dropdown     | Canary-Qwen 2.5B        | Only option in v1                      |
| Audio chunk size    | Slider 3–10s | 6s                      | Larger = fewer API calls, more latency |
| Chunk overlap       | Slider 0–1s  | 0.5s                    | Reduces word cuts at boundaries        |
| Inference device    | Dropdown     | Auto (MPS)              | Auto / MPS / CPU                       |
| Model status        | Info label   | "Loaded · 5.1 GB · mps" |                                        |
| Re-download model   | Button       | —                       | Clears cache and re-downloads          |


### Tab 4 — Notes


| Setting                     | Type              | Default                            |
| --------------------------- | ----------------- | ---------------------------------- |
| Temperature                 | Slider 0.0–1.0    | 0.2                                |
| Max output tokens           | Slider 1000–16000 | 8192                               |
| Default note language       | Dropdown          | English                            |
| Include YAML front matter   | Toggle            | On                                 |
| Front matter tags format    | Text              | `[{course_lower}, lecture, notes]` |
| Custom system prompt suffix | Textarea          | (blank)                            |


---

## 14. Data & Config Storage

All data stored in macOS standard locations:

```
~/Library/Application Support/Scout/
    config.json              # all settings
    courses.json             # course list (may merge into config.json)

~/Library/Logs/Scout/
    scout.log                # rotating log file

~/.cache/huggingface/hub/
    models--nvidia--canary-qwen-2.5b/   # model weights (managed by HF Hub)
```

### `config.json` schema

```json
{
  "version": "1.0",
  "vault_path": "/Users/aayush/Documents/obsidian/great-days",
  "google_api_key": "AIza...",
  "gemma_model": "gemma-4-31b-it",
  "temperature": 0.2,
  "max_tokens": 8192,
  "chunk_seconds": 6,
  "chunk_overlap": 0.5,
  "inference_device": "auto",
  "auto_open_obsidian": false,
  "prevent_sleep": true,
  "show_waveform": true,
  "record_shortcut": "Cmd+R",
  "include_frontmatter": true,
  "frontmatter_tags": "[{course_lower}, lecture, notes]",
  "custom_prompt_suffix": "",
  "courses": [
    {
      "id": "uuid-here",
      "name": "CS446",
      "folder": "CS446",
      "color": "#2980B9"
    }
  ]
}
```

---

## 15. Error Handling Strategy


| Error                           | Handling                                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Microphone permission denied    | Show macOS permission prompt via `AVCaptureDevice`; if denied, show instructions to enable in System Settings > Privacy > Microphone |
| Canary-Qwen not downloaded      | Disable record button; show "Download model in Settings" banner                                                                      |
| Canary-Qwen inference failure   | Show inline error in transcript panel; continue recording; retry next chunk                                                          |
| Google API key missing          | Disable "Generate Notes" button; show "Add API key in Settings" tooltip                                                              |
| Google API rate limit / error   | Show error dialog with retry button; preserve transcript                                                                             |
| Obsidian vault path not found   | Show warning on save; offer to pick new vault path                                                                                   |
| Vault subfolder missing         | Auto-create folder silently                                                                                                          |
| File already exists             | Confirmation dialog: Overwrite / Save as Lecture-XX-2.md / Cancel                                                                    |
| No internet for Google API      | Show "No internet connection" status; transcript still works (local)                                                                 |
| Out of memory during model load | Show error with suggestion to close other apps; fall back to CPU                                                                     |


---

