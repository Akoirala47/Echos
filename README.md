# Echos

![macOS](https://img.shields.io/badge/macOS-13%2B-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-green)

**Echos** is a native macOS app that turns your lectures into structured Obsidian notes — named after Koichi Hirose's stand from JoJo's Bizarre Adventure Part 4.

It transcribes your microphone locally using [Whisper large-v3](https://huggingface.co/openai/whisper-large-v3) — running entirely on Apple Silicon via Metal Performance Shaders — then sends the transcript to Gemma 4 31B (via Google AI) to produce clean, formatted markdown notes. Notes are saved directly into your Obsidian vault with YAML front matter injected automatically.

**Your audio never leaves your Mac.**

---

## Features

- **Live transcription** — Whisper large-v3 runs on-device (MPS). Updates the transcript panel every ~6 seconds.
- **Structured notes** — Gemma 4 31B converts the full transcript into headings, bullet points, code blocks, and a Key Takeaways section.
- **Obsidian-native** — Saves to `{vault}/{course}/Lecture-NN.md` with YAML front matter. Auto-increments lecture numbers. Opens the note in Obsidian with one click.
- **Fully offline transcription** — No audio is sent to any server.
- **Pause / Resume** — Pause recording mid-lecture without losing the transcript.
- **Editable at every step** — Edit the transcript before generating notes; edit the notes before saving.
- **Regenerate with instructions** — Hit "Regenerate…" and add a custom focus (e.g. "emphasise the proof steps").
- **Dark mode** — Follows your macOS appearance setting automatically.

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS 13 (Ventura) or later | Required |
| Apple Silicon (M1+) | Strongly recommended (MPS inference). Intel Macs work with CPU-only mode. |
| [Obsidian](https://obsidian.md) | Must be installed. Echos does not create the vault. |
| Google AI API key | Free tier available at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| ~4 GB free disk space | ~620 MB for the app + ~3 GB for Whisper large-v3 (downloaded on first launch) |

---

## Install (pre-built DMG)

1. Download `Echos-1.0.x.dmg` from the [latest release](../../releases/latest).
2. Open the DMG and drag **Echos.app** into your **Applications** folder.
3. Launch Echos from Launchpad or Spotlight.

> **Gatekeeper note:** Because Echos is not yet notarised with an Apple Developer certificate, macOS will block it on first launch. To open it anyway: right-click **Echos.app** → **Open** → click **Open** in the dialog. You only need to do this once.

---

## First-launch walkthrough

Echos shows a three-step setup wizard the first time you open it:

1. **Welcome** — Overview of what Echos needs.
2. **Configure** — Set your Obsidian vault folder and paste your Google AI API key. Echos validates the key before you can continue.
3. **Download model** — Whisper large-v3 (~3 GB) downloads once to `~/.cache/huggingface/hub/`. Click **Background** to explore the app while downloading; the record button re-enables once the model is ready.

---

## Using Echos

1. **Add a course** — Click **+ Add Course** in the sidebar, enter a name and vault subfolder, and pick a colour.
2. **Select the course** — Click it in the sidebar. Echos auto-detects the next lecture number.
3. **Record** — Click **Start Recording** (or press **⌘R**). The transcript panel updates live.
4. **Stop** — Click **Stop Recording** (or press **⌘R** again).
5. **Generate notes** — Click **Generate Notes**. Notes stream in as Gemma processes the transcript.
6. **Save** — Click **Save to Obsidian** in the status bar, then **Open in Obsidian** to jump straight to the note.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| ⌘R | Start / Stop recording |
| ⌘P | Pause / Resume recording |
| ⌘, | Settings |
| ⌘S | Save note |
| ⌘N | New recording |

---

## Settings

Open **Echos → Settings** (⌘,) to configure:

| Tab | Key settings |
|---|---|
| **General** | Vault path, auto-open in Obsidian, prevent-sleep, waveform, record shortcut |
| **API Keys** | Google AI API key, Gemma model ID, test connection |
| **Transcription** | Chunk size (3–10 s), overlap (0–1 s), inference device (Auto / MPS / CPU), re-download model |
| **Notes** | Temperature, max tokens, language, YAML front matter toggle, tags template, custom prompt suffix |

---

## Developer setup

```bash
# 1. Clone
git clone https://github.com/Akoirala47/Echos.git
cd Echos

# 2. Install libsndfile (required by soundfile)
brew install libsndfile

# 3. Create a Python 3.11 virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Install runtime + dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 5. Run from source
python -m echos.main
```

### Running tests

```bash
pytest tests/ -v
```

All tests are pure unit tests with no network or model dependencies. Expected coverage ≥ 80% across `config`, `core`, and `utils`.

---

## Building the DMG

```bash
# Requires: brew install create-dmg
chmod +x build/build.sh
./build/build.sh
# Output: dist/Echos-1.0.x.dmg
```

The build script:
1. Generates placeholder icon and DMG background (`python3 assets/create_assets.py`).
2. Bundles the app with **py2app** (Python runtime embedded; no user install needed).
3. Packages the bundle into a drag-install `.dmg` with **create-dmg**.

### Code signing (optional, for Gatekeeper-free distribution)

```bash
# Requires an Apple Developer account ($99/yr)
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  --entitlements build/entitlements.plist \
  --options runtime \
  dist/Echos.app

xcrun notarytool submit dist/Echos-1.0.x.dmg \
  --apple-id "your@email.com" \
  --password "@keychain:AC_PASSWORD" \
  --team-id "TEAMID" \
  --wait

xcrun stapler staple dist/Echos-1.0.x.dmg
```

### CI/CD

Pushing a `v*` tag (e.g. `v1.0.5`) triggers the GitHub Actions workflow (`.github/workflows/build.yml`), which builds the DMG on an M1 runner and attaches it to the GitHub Release automatically.

---

## Project structure

```
Echos/
├── echos/
│   ├── main.py            # Entry point
│   ├── app.py             # AppController — state machine + signal wiring
│   ├── core/
│   │   ├── audio_worker.py      # QThread: mic capture + Whisper inference
│   │   ├── model_manager.py     # Download, load, transcribe (Whisper large-v3)
│   │   ├── notes_worker.py      # QThread: Gemma via Google AI (streaming)
│   │   └── obsidian_manager.py  # Vault path ops, file write, lecture numbering
│   ├── ui/
│   │   ├── main_window.py       # QMainWindow layout
│   │   ├── sidebar.py           # Course list
│   │   ├── record_bar.py        # Record button + waveform + timer
│   │   ├── transcript_panel.py  # Live transcript editor
│   │   ├── notes_panel.py       # Rendered markdown notes
│   │   ├── status_bar.py        # Status + Save button
│   │   ├── onboarding.py        # First-launch wizard
│   │   └── settings_window.py   # Settings dialog
│   ├── config/
│   │   ├── config_manager.py    # Atomic JSON read/write
│   │   └── defaults.py          # Default config values
│   └── utils/
│       ├── audio_utils.py       # RMS, chunk splitting, deduplication
│       ├── dialogs.py           # Centralised dialog helpers
│       ├── frontmatter.py       # YAML front matter injector
│       ├── markdown.py          # Gemma prompt builder
│       └── theme.py             # Dark mode detection + theme colours
├── assets/
│   ├── create_assets.py   # Generates icon.icns + dmg_background.png
│   ├── icon.icns
│   ├── icon_512.png
│   └── dmg_background.png
├── build/
│   ├── setup.py           # py2app config
│   ├── build.sh           # Full build pipeline
│   └── entitlements.plist # macOS sandbox entitlements
└── tests/                 # pytest unit tests
```

---

## Data stored on your Mac

| Location | Contents |
|---|---|
| `~/Library/Application Support/Echos/config.json` | All settings, course list, API key |
| `~/Library/Logs/Echos/echos.log` | Rotating log file (10 MB × 3) |
| `~/.cache/huggingface/hub/` | Whisper large-v3 model weights (~3 GB) |

---

## License

MIT — see [LICENSE](LICENSE).
