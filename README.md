# Echos

![macOS](https://img.shields.io/badge/macOS-13%2B-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-green)

**Echos** is a native macOS app that records spoken audio, transcribes it entirely on-device using Whisper large-v3, then uses Gemma 4 31B (via Google AI) to turn the raw transcript into clean, structured Obsidian markdown notes — automatically saved to your vault with proper YAML front matter.

**Your audio never leaves your Mac.** Only the text transcript is sent to Google's API for note generation.

---

## What makes it different

Most transcription tools are cloud-first. Echos runs Whisper locally on Apple Silicon via Metal Performance Shaders, so every word you say is processed on your own hardware. The privacy boundary is the transcript, not the audio. Works for lectures, meetings, interviews, talks, brainstorms — anything spoken.

---

## Requirements

| | |
|---|---|
| macOS 13 Ventura or later | Required |
| Apple Silicon (M1 or newer) | Strongly recommended. Intel Macs fall back to CPU inference, which is slower but functional. |
| [Obsidian](https://obsidian.md) installed | Echos writes notes into an existing vault; it does not create one. |
| Google AI API key | Free tier works. Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). |
| ~4 GB free disk space | ~620 MB for the bundled app + ~3 GB for Whisper large-v3, downloaded on first launch. |

---

## Install

1. Download `Echos-1.0.x.dmg` from the [latest release](../../releases/latest).
2. Open the DMG and drag **Echos.app** into `/Applications`.
3. Launch from Launchpad or Spotlight.

> **Gatekeeper:** Echos is not yet notarised with an Apple Developer certificate. On first launch macOS will block it. Right-click **Echos.app → Open → Open** to bypass this once. You will not be prompted again.

---

## First launch

A three-step wizard runs automatically the first time Echos opens.

**Step 1 — Welcome.** A brief overview of what permissions and resources Echos needs.

**Step 2 — Configure.** Set your Obsidian vault root folder (the top-level directory Obsidian opens, not a subfolder inside it). Paste your Google AI API key. Echos validates the key against the API before letting you continue — it will not accept a key that is malformed or revoked.

**Step 3 — Download model.** Whisper large-v3 (~3 GB) is downloaded from HuggingFace into `~/.cache/huggingface/hub/`. A progress bar shows GB downloaded vs total. Click **Background** to dismiss the wizard and explore the app while the download continues; the Start Recording button stays disabled and re-enables automatically once the model finishes loading.

If you close the app mid-download, Echos resumes from where it left off on the next launch — it never re-downloads files that are already on disk.

---

## The interface

The window has five zones.

### Sidebar (left, 248 px)

**Vault header.** Shows the vault name and its parent directory path (`~/Obsidian`, `~/Documents`, etc.). This updates whenever you change the vault path in Settings.

**VAULT section.** A live tree view of your entire Obsidian vault on disk. Folders expand and collapse with a click. `.md` note files appear as leaves. The tree is backed by `QFileSystemWatcher` — if you create, rename, or delete a file in Obsidian or Finder while Echos is open, the tree refreshes within about one second without you doing anything. The currently targeted folder is highlighted with your topic's accent color. Hover over any folder to reveal a **"Rec here"** affordance that lets you drop a one-off note into that folder without creating a full topic. Click **+** to create a new subfolder. Click **⟳** to force a manual rescan.

**TOPICS section.** Named bookmarks that point at vault-relative folder paths. Each topic has a color dot and a two-segment path hint (e.g. `CS446 / Lectures`). Clicking a topic selects it as the active recording context, highlights its folder in the vault tree, and auto-detects the next session number. Right-click a topic to delete it (this only removes it from Echos — vault files are untouched). Drag topics to reorder them. Click **+** to add a new topic.

**Settings button.** At the bottom, opens the Settings dialog.

### Record bar (top of content area)

**Header row.** Shows the active topic's color dot, bold name, and a breadcrumb path (e.g. `School  ›  CS446  ›  Lectures`). On the right is a **Session N** number input. Echos auto-fills this by scanning the target folder for existing `Lecture-NN.md` files and incrementing the highest number found — if you have `Lecture-01.md` through `Lecture-04.md`, it pre-fills 5. You can override it by typing directly into the field before recording.

**Controls row.** The primary action button, a status pill, the waveform, and the elapsed timer.

### Transcript panel (left panel)

Editable plain-text area. Text appears here as Whisper processes each audio chunk, roughly every 6 seconds. You can edit freely at any time — add punctuation, fix names, remove tangents — because notes are generated from whatever text is in this panel when you click Generate Notes, not from the raw audio buffer. The panel remembers your edits across pause/resume cycles. **Clear** wipes it. **Export .txt** saves the raw text to a file.

### Notes panel (right panel)

Rendered markdown preview by default. Toggle **Raw** to switch to a plain-text editor where you can hand-edit the markdown before saving. **Copy** puts the current content on the clipboard. The bottom footer shows **Generate Notes**, **Regenerate…**, and a chip showing the model name and streaming status.

### Status bar (bottom strip)

Left side: a state dot and label (`Ready`, `Recording`, `Paused`, `Session complete`, `Generating notes…`, `Notes ready`, `Saved · filename.md`). Center: the vault path. Right side: context-sensitive action buttons.

---

## Recording flow in detail

### Starting a session

Click **Start Recording** (or press **⌘R**). Echos:
1. Checks the model is loaded. If not, shows a warning.
2. Checks a topic is selected. If not, shows a warning.
3. Opens a `sounddevice.InputStream` at 16 kHz, mono, float32, with 100 ms audio blocks fed through a callback on a PortAudio thread.
4. Starts `AudioWorker` on a background QThread. The worker accumulates raw PCM samples into a rolling numpy buffer.
5. Emits `audio_level` at ~30 fps by averaging the last 10 RMS measurements. This drives the waveform animation — bars respond to real microphone volume.
6. Activates a macOS power assertion (`NSProcessInfo.beginActivityWithOptions`) to prevent the system from sleeping mid-session.
7. Sets a red dot badge on the Dock icon so you can see at a glance that capture is running even when the window is hidden.

### How transcription works under the hood

Every N seconds (default 6, configurable 3–10), the audio worker checks whether the rolling buffer has accumulated enough samples for a full chunk. When it does:

1. It slices `chunk_samples` worth of float32 PCM from the buffer.
2. It passes the slice to `ModelManager.transcribe()`, which runs on the same background thread.
3. The processor pads or truncates to exactly 30 seconds of audio (Whisper's native context window), converts to mel-spectrogram features, casts to `float16` on MPS or `float32` on CPU to match the model weights, and runs a single forward pass with `model.generate()`.
4. The resulting token IDs are decoded back to text with special tokens stripped.
5. **Overlap deduplication:** chunks overlap by `overlap_seconds` (default 0.5 s) to avoid clipping words at boundaries. After each transcription, `deduplicate_overlap()` finds the longest word sequence that appears at the end of the previous transcript and the beginning of the new one, and removes the duplicate. Only genuinely new words are appended.
6. The deduplicated text is emitted as a `transcript_chunk` signal and appended to the transcript panel on the main thread.
7. After slicing, the buffer is trimmed to the overlap tail — old audio is discarded so memory stays bounded.

A transcription error on one chunk is logged and emitted as a non-fatal `error` signal (shows in the status bar). Recording continues on the next chunk.

### Pause and Resume

**⌘P** or the Pause button suspends audio accumulation without closing the stream. The mic remains open so there is no latency spike when you resume. The PortAudio callback keeps firing, but the worker stops appending samples to its buffer while `pause_event` is cleared. The waveform dims to ~35% opacity to visually indicate the paused state. The elapsed timer stops. Resuming is instantaneous.

Pause does not finalise anything. You can pause and resume as many times as you want within a session, and the transcript accumulates continuously.

### Ending a session

**End Session** appears in the status bar (right side) whenever you are recording or paused. It is also in **File → End Session (⌘⇧E)**. Clicking it shows a confirmation dialog — ending a session is irreversible in the sense that you cannot add more audio to the same session afterwards. Confirming:

1. Stops the AudioWorker (sets the stop event, waits up to 5 seconds for the thread to exit cleanly).
2. Ends the macOS power assertion so the system can sleep normally.
3. Removes the Dock badge.
4. Transitions to `Session complete` state. The Generate Notes button becomes active.

The **Start New Session** button (status bar, or **⌘N**) resets the transcript and notes panels and returns to idle without prompting, since the old session is already closed.

---

## Note generation

### What gets sent where

Clicking **Generate Notes** takes the full text currently in the transcript panel and sends it to Google's Gemini API (model: `gemma-4-31b-it` by default). This is the only network call in the entire flow. The request is structured as:

- **System instruction:** A concise note-taker persona with explicit output rules (no preamble, start immediately with `# Title`, use `##` for topics, bold key terms on first use, code blocks for formulas/code, end with `## Key Takeaways`). The system instruction is passed separately from the user message so the model treats it as standing instructions rather than content to echo.
- **User turn:** Session name, number, date, and the raw transcript. Nothing else.

This separation was deliberate — earlier versions put everything in one prompt as a "Rules:" block, which caused Gemma to reason through the rules out loud and include that reasoning in the output.

### Streaming

The API response streams back incrementally. Each text chunk is emitted as a `chunk_ready` signal, appended to the internal markdown buffer, re-rendered to HTML, and displayed in the notes panel in real time. You see notes appear word-by-word as Gemma generates them. Empty chunks from the stream (finish-reason or usage-metadata packets) are filtered out silently.

### Regenerating with a custom focus

**Regenerate…** opens a small text dialog. Whatever you type there is appended to the system instruction as `Additional focus: <your text>` before re-running the same request against the current transcript. Examples of useful regeneration prompts:

- `"focus on the mathematical proofs and derivations"`
- `"emphasise action items and decisions"`
- `"write in a more concise, bullet-point-only style"`
- `"include more detail on the Q&A section at the end"`

The original transcript is unchanged; only the notes are replaced.

---

## Saving to Obsidian

**Save to Obsidian** appears in the status bar once notes are ready. It:

1. Resolves the save path: `{vault_root}/{topic_folder}/Lecture-{NN:02d}.md`. The folder is created automatically if it does not exist, including all intermediate directories.
2. Checks whether the file already exists. If it does, shows a dialog with three choices: Overwrite, Save with the next available number, or Cancel.
3. If YAML front matter is enabled (default on), prepends a front matter block:
   ```yaml
   ---
   course: CS446
   lecture: 5
   date: 2026-04-25
   tags: [cs446, notes]
   echos_version: 1.0.0
   ---
   ```
   The `tags` field uses a configurable template with a `{course_lower}` placeholder so tags are automatically lowercased.
4. Writes the file atomically — actually it uses `Path.write_text()` which is a standard posix write.
5. Transitions to `Saved` state. The Save button turns green and shows the filename.

After saving, **Open in Obsidian** appears. This invokes `obsidian://open?vault={vault_name}&file={path}` via macOS's `open` command, which hands off to the Obsidian URI handler. Obsidian opens and navigates directly to the note. The vault name and file path are URL-encoded so spaces and special characters in folder names work correctly.

---

## Keyboard shortcuts

| Shortcut | Action | Notes |
|---|---|---|
| ⌘R | Start recording (when idle) or Resume (when paused) | Does nothing when actively recording |
| ⌘P | Pause (when recording) | Does nothing otherwise |
| ⌘⇧E | End Session | Shows confirm dialog |
| ⌘N | New recording | Resets panels, returns to idle |
| ⌘S | Save note | Only active after notes are generated |
| ⌘, | Settings | |

The record shortcut (`⌘R`) is configurable in Settings → General if it conflicts with another app.

---

## Settings

Open **Echos → Settings (⌘,)**.

### General

- **Vault path.** The root directory of your Obsidian vault. Must be the same path Obsidian uses — Echos passes it directly to the `obsidian://` URI.
- **Auto-open in Obsidian after saving.** If on, Echos calls the Obsidian URI automatically after every save without waiting for you to click the button.
- **Prevent sleep during recording.** Uses `NSProcessInfo.beginActivityWithOptions(NSActivityLatencyCritical)` to hold a power assertion. Laptops on battery won't sleep mid-session. Enabled by default.
- **Show waveform.** Toggles the animated bar visualiser in the record bar. When off, the waveform area is blank.
- **Record shortcut.** The key combination that starts/resumes recording. Default `⌘R`. Changes take effect immediately without restarting.

### API Keys

- **Google AI API key.** Stored in `config.json`. Never transmitted anywhere except the Google API endpoint.
- **Gemma model ID.** Defaults to `gemma-4-31b-it`. You can change this to any model ID supported by the Google Generative AI SDK — for example `gemini-2.0-flash` if you want faster, lower-cost generation. The field accepts any string so it won't break if a new model is released.
- **Test Connection.** Sends a minimal request to verify the key is valid and the selected model is accessible before you commit the settings.

### Transcription

- **Chunk size (3–10 s).** How many seconds of audio Whisper processes at a time. Smaller chunks mean more frequent transcript updates but more total inference calls. Larger chunks are more accurate (more context) but the transcript updates less often. Default 6 s.
- **Overlap (0–1 s).** How many seconds of audio are re-fed into each chunk from the end of the previous one. Prevents words at chunk boundaries from being clipped or dropped. The overlap deduplication algorithm removes the repeated words automatically. Default 0.5 s.
- **Inference device.** Auto (uses MPS on Apple Silicon, falls back to CPU), MPS, or CPU. MPS is approximately 5–10× faster than CPU for Whisper large-v3. CPU mode is available for Intel Macs or if MPS is giving unexpected results.
- **Re-download model.** Deletes the local HuggingFace cache for Whisper large-v3 and re-downloads it. Useful if weights become corrupt or a newer model version is released.

### Notes

- **Temperature (0.0–1.0).** Controls how deterministic Gemma's output is. Lower values (0.1–0.3) produce more predictable, structured output. Higher values introduce more variation. Default 0.2 works well for note-taking.
- **Max tokens.** The maximum number of tokens Gemma can generate in one response. Default 8192. Increase if your notes are being cut off mid-section. Decrease if you want a cost ceiling.
- **Output language.** Passed as context to Gemma. If your lectures are in English but you want notes in Spanish, set this to Spanish. Default English.
- **Include YAML front matter.** When on, the saved `.md` file starts with a YAML block containing course, lecture number, date, tags, and Echos version. Obsidian renders this as structured Properties. When off, the file starts directly with the markdown heading.
- **Tags template.** Controls the `tags:` line in the front matter. Supports `{course_lower}` which is replaced with the lowercased topic name. Default `[{course_lower}, notes]`.
- **Custom prompt suffix.** Free-text appended to the system instruction for every generation. Use this for standing instructions that apply to all your notes: `"always include a definitions section"`, `"never use passive voice"`, `"add an exam questions section at the end"`, etc. This is separate from the per-regeneration focus instruction.

---

## Under the hood

### Audio pipeline

```
Microphone
    │  PortAudio callback (100 ms blocks, 16 kHz float32)
    │
    ▼
AudioWorker (background QThread)
    │  Rolling numpy buffer (unbounded growth prevented by trimming)
    │  RMS computed per-block, averaged over a 10-sample deque
    │  audio_level signal → waveform at 30 fps
    │
    ▼ (every N seconds of accumulated audio)
ModelManager.transcribe()
    │  WhisperProcessor: pad/truncate to 30 s → mel features → float16
    │  model.generate() with MPS/CPU via PyTorch
    │  batch_decode → strip special tokens → plain text
    │
    ▼
deduplicate_overlap()  — removes words repeated at chunk boundaries
    │
    ▼
transcript_chunk signal → main thread → TranscriptPanel.append_text()
```

### Note generation pipeline

```
Transcript text (from panel)
    │
    ▼
NotesWorker (background QThread)
    │  system_instruction (model persona + output rules)
    │  user turn (session name, date, transcript)
    │  GenerativeModel.generate_content(stream=True)
    │
    ▼ streaming chunks
chunk_ready signal → main thread → NotesPanel.append_chunk()
    │  markdown accumulated in memory
    │  re-rendered to HTML on each chunk
    │
    ▼ (stream complete)
done signal → NotesPanel.set_notes()
```

### Thread model

Echos uses three background threads beyond the main Qt event loop:

- **AudioWorker (QThread).** Runs the PortAudio stream and transcription loop. All internal state mutations happen on this thread. Cross-thread communication uses Qt signals (queued connections), which are thread-safe by design.
- **ModelManager load worker (inline QThread).** Loads model weights from disk on startup. Emits a `finished` signal when done. If loading fails, emits `load_failed` with the error message.
- **NotesWorker (QThread).** Makes the streaming API call and emits each text chunk. The stream runs synchronously inside `run()` so no additional threading is needed.
- **VaultWatcher.** Not a thread — `QFileSystemWatcher` is event-driven, posting callbacks on the main thread when the filesystem changes.

### Config persistence

Settings are stored in `~/Library/Application Support/Echos/config.json`. Writes use a write-then-rename strategy: a temp file is written in the same directory, then `os.replace()` atomically swaps it in. This means a crash mid-save never corrupts the config — either the old file survives intact or the new one is fully written, never a partial write.

On load, Echos merges the saved config with the compiled-in defaults. Keys that exist in defaults but not in the saved file pick up the default value. This makes forward-compatibility straightforward — new settings added in future versions are silently filled with sensible defaults when loading an older config file.

### Vault file watching

`VaultWatcher` wraps `QFileSystemWatcher` and watches the vault root recursively up to 5 directory levels deep. When any directory or file changes:

1. The watcher's callback fires on the main thread (Qt signal/slot).
2. If a directory was added, it is immediately added to the watch list (new subdirectories would otherwise be invisible until the next restart).
3. The sidebar's vault tree is rescanned by calling `load_vault()` again, which rebuilds the `QTreeWidget` from the current disk state.

The watcher automatically starts when you set a vault path (either during onboarding or by changing it in Settings) and stops when the vault path is cleared or changed.

### Model dtype handling

Whisper large-v3 loads as `float16` on MPS and `float32` on CPU. The HuggingFace processor always returns `float32` input features regardless of device. Without an explicit cast, PyTorch raises a runtime error about mismatched input and bias types. Echos explicitly casts `inputs["input_features"]` to the model's dtype immediately before each forward pass.

---

## Project structure

```
echos/
├── main.py               Entry point: logging, audio lib patching, QApplication
│                         setup (Fusion style + warm QPalette), onboarding, main window
├── app.py                AppController: state machine, signal wiring, all business logic
│
├── core/
│   ├── audio_worker.py   QThread: mic capture loop, RMS, transcription scheduling
│   ├── model_manager.py  Whisper download/load/transcribe, ModelDownloadWorker
│   ├── notes_worker.py   QThread: Gemma streaming API call
│   ├── obsidian_manager.py Vault filesystem ops: lecture numbering, write, open URI
│   └── vault_watcher.py  QFileSystemWatcher wrapper: live vault tree sync
│
├── ui/
│   ├── main_window.py    QMainWindow: layout assembly, menu bar
│   ├── sidebar.py        Vault tree (QTreeWidget) + topics list + VaultWatcher wiring
│   ├── record_bar.py     Two-row bar: topic header + Start/Pause/Resume + waveform
│   ├── transcript_panel.py  Editable live transcript
│   ├── notes_panel.py    Rendered markdown preview / raw edit + generate footer
│   ├── status_bar.py     State dot + vault path + End Session / Save / Open buttons
│   ├── onboarding.py     Three-step first-launch wizard
│   ├── settings_window.py  Four-tab settings dialog
│   └── widgets/
│       ├── waveform.py   36-bar QPainter waveform with time-based sine animation
│       ├── course_item.py  Sidebar topic row delegate
│       └── model_progress.py  Download progress bar widget
│
├── config/
│   ├── config_manager.py Atomic JSON load/save with defaults merge
│   └── defaults.py       Compiled-in default values for all settings
│
└── utils/
    ├── audio_utils.py    compute_rms, split_into_chunks, deduplicate_overlap
    ├── dialogs.py        Shared dialog helpers (ask_yes_no, show_error, etc.)
    ├── frontmatter.py    YAML front matter injector with tag template rendering
    ├── markdown.py       Gemma system instruction + user prompt builder
    └── theme.py          Warm parchment design tokens (light mode, no branching)
```

---

## Data on your Mac

| Location | What is stored |
|---|---|
| `~/Library/Application Support/Echos/config.json` | All settings, topic list, Google API key |
| `~/Library/Logs/Echos/echos.log` | Rotating log (10 MB × 3 backups). Contains transcription timings, API latency, save operations, and any errors. |
| `~/.cache/huggingface/hub/models--openai--whisper-large-v3/` | Whisper large-v3 weights (~3 GB). Shared with any other HuggingFace tools on your machine. |

---

## Developer setup

```bash
# 1. Clone
git clone https://github.com/Akoirala47/Echos.git
cd Echos

# 2. Install libsndfile (required by soundfile / PortAudio)
brew install libsndfile

# 3. Python 3.11 virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 5. Run from source
python -m echos.main
```

Logs are written to `~/Library/Logs/Echos/echos.log` and mirrored to stdout at DEBUG level in development.

### Running tests

```bash
pytest tests/ -v
```

All tests are pure unit tests — no network, no model weights, no Qt event loop required. Coverage is measured across `config/`, `core/`, and `utils/`.

---

## Building the DMG

```bash
brew install create-dmg
chmod +x build/build.sh
./build/build.sh
# Output: dist/Echos-1.0.x.dmg
```

The build script: generates app icon and DMG background assets, bundles the entire Python runtime and all dependencies into a self-contained `.app` with py2app, packages it into a drag-install DMG. The bundled app includes `libsndfile` and `libportaudio` directly in `Contents/Frameworks/` with a patched `ctypes.util.find_library` so PortAudio and soundfile find their native libraries inside the bundle rather than looking for Homebrew paths that don't exist on other machines.

### Code signing and notarisation

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  --entitlements build/entitlements.plist \
  --options runtime \
  dist/Echos.app

xcrun notarytool submit dist/Echos-1.0.x.dmg \
  --apple-id "you@example.com" \
  --password "@keychain:AC_PASSWORD" \
  --team-id "TEAMID" \
  --wait

xcrun stapler staple dist/Echos-1.0.x.dmg
```

The entitlements file grants microphone access (`com.apple.security.device.audio-input`) and outbound network (`com.apple.security.network.client`) for the Google API call. Both are required for notarisation.

### CI/CD

Pushing a `v*` tag triggers the GitHub Actions workflow which runs the full build on a macOS Apple Silicon runner and attaches the signed DMG to the GitHub Release automatically.

---

## License

MIT — see [LICENSE](LICENSE).
