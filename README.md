# Echos

**Local AI Transcription & Automated Note-Taking for macOS**

**Echos** is a native, privacy-first macOS application that records spoken audio, transcribes it entirely on-device using **Whisper large-v3**, and leverages **Gemma 4 31B** (via Google AI Studio) to automatically generate clean, structured Markdown notes directly into your **Obsidian** vault.

Designed specifically to run on Apple Silicon, Echos transforms lectures, meetings, interviews, and brainstorms into polished knowledge bases, all while ensuring your raw audio never leaves your Mac. 

---

## Features & Benefits

- **100% Local Audio Transcription**: Powered by **Whisper large-v3** running locally on Apple's Metal Performance Shaders (MPS). Your privacy boundary is the text transcript—no raw audio is ever uploaded to the cloud.
- **Automated Obsidian Integration**: Directly writes formatted `.md` notes into your Vault, complete with custom YAML front matter (tags, course/topic names, dates). Includes a live filesystem watcher (`QFileSystemWatcher`) that instantly synchronizes the app's sidebar with your Obsidian folders.
- **Intelligent Note Generation**: Turns chaotic raw transcripts into cleanly structured study notes using Gemma 4 31B (or any compatible Google AI model). Built-in filtering strips out LLM reasoning/thinking tags (`<thinking>`) to guarantee pristine final outputs.
- **Elegant Native Interface**: Features a comprehensive V2 UI overhaul. Enjoy a "warm parchment" aesthetic with seamless macOS window integration, an interactive Markdown previewer, and a beautifully animated real-time sine-wave audio visualizer.
- **Advanced Session Management**: Seamlessly pause and resume recordings without breaking context. Overlapping speech chunks are intelligently deduplicated on the fly, ensuring a flawless continuous transcript.

---

## Requirements


| Requirement  | Details                                                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **macOS**    | 13 Ventura or later required.                                                                                                                          |
| **Hardware** | **Apple Silicon (M1/M2/M3/M4)** strongly recommended for real-time MPS inference. Intel Macs will fall back to CPU inference (functional, but slower). |
| **Note App** | [Obsidian](https://obsidian.md) installed. Echos populates an existing vault; it does not create a new one.                                            |
| **API Key**  | **Google AI API key** (Free tier works perfectly). Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).                        |
| **Storage**  | 4 GB free disk space (~620 MB for the app + ~3 GB for the Whisper model, downloaded on first launch).                                                  |


---

## Installation

1. Download `Echos-2.0.x.dmg` from the [Releases page](https://github.com/Akoirala47/Echos/releases).
2. Open the `.dmg` and drag **Echos.app** into your `/Applications` folder.
3. Launch from Launchpad or Spotlight.

> **Note on Gatekeeper:** Echos is currently unsigned with an Apple Developer certificate. On first launch, macOS may block it. Right-click **Echos.app → Open → Open** to bypass this protection once. You will not be prompted again.

---

## Getting Started

A simple, three-step onboarding wizard will run automatically the first time you open Echos.

1. **Welcome**: A brief overview of permissions.
2. **Configure**: Select your **Obsidian Vault** root folder (the top-level directory, not a subfolder) and securely paste your Google AI API key. Echos validates the key immediately.
3. **Model Download**: Echos automatically fetches the Whisper large-v3 model (~~3 GB) from HuggingFace to `~~/.cache/huggingface/hub/`. You can dismiss the wizard to background the download. *If interrupted, the download will cleanly resume on next launch.*

---

## Interface & Usage

### The Sidebar (Live Vault Tree)

- **Live Sync**: Displays a live tree of your Obsidian vault. Create, delete, or rename files in Finder/Obsidian, and Echos updates instantly. 
- **Topics**: Set up custom "Topics" mapped to vault subfolders. Selecting a topic auto-detects existing note sequences (e.g., if you have `Lecture-04.md`, it pre-fills `5` for your next session).

### The Record Bar

Features a responsive, time-based animated waveform that reflects real microphone RMS volume. Hit **Start Recording (⌘R)** to begin capturing audio. The app actively prevents your Mac from sleeping during a session. 

### The Transcription Engine

Every 6 seconds (configurable), Echos processes your audio chunk through Whisper. You will see the text stream into the **Transcript Panel** on the left.

- **Overlap Deduplication**: Prevents clipping and dropped words by overlapping audio chunks and programmatically stripping duplicates. 
- **Live Editing**: You can manually edit the live transcript as you record—add names, fix acronyms, or remove tangents.

### Note Generation

Once you hit **End Session (⌘⇧E)**, click **Generate Notes**.

- Echos sends the finalized transcript to Google's API along with a strict formatting persona. 
- The resulting Markdown streams in real-time into the **Notes Panel**.
- Not happy with the focus? Click **Regenerate...** and provide custom guidance (e.g., *"Focus on the mathematical formulas"* or *"Write in a concise bullet-point style"*).

### Saving to Obsidian

Click **Save to Obsidian (⌘S)**. The app injects YAML front matter and writes the file safely. You can then click **Open in Obsidian** to instantly jump to your new note.

---

## ⚙️ Configuration & Settings

Access Settings via **Echos → Settings (⌘,)**.

- **Transcription Settings**: Adjust chunk size (3–10s) and overlap duration (0–1s) to balance transcription latency vs. accuracy. Switch inference mode between `Auto`, `MPS` (Metal), and `CPU`.
- **Note Settings**: Tweak LLM temperature (default `0.2` for highly structured notes), max tokens, and output language. 
- **Custom Prompts**: Append persistent custom instructions to the AI (e.g., *"always include a glossary at the bottom"*).
- **YAML Templates**: Customize the Front Matter tags injected into Obsidian using dynamic placeholders like `{course_lower}`.

---

## 🛠️ Architecture & Under the Hood

### Audio Pipeline

Audio is captured via a `sounddevice` PortAudio stream (16 kHz, mono, float32) running on a background `QThread`. Audio is accumulated in a rolling numpy buffer and periodically passed to PyTorch for `float16` feature extraction and inference.

### State & Thread Management

Echos maintains a responsive GUI utilizing multiple background threads:

- **AudioWorker (`QThread`)**: Manages the mic stream and transcription queue.
- **NotesWorker (`QThread`)**: Handles the streaming Gemini API network call.
- **VaultWatcher**: A `QFileSystemWatcher` wrapper that triggers main-thread Qt slots on file changes.

### Config Safety

Configuration (`~/Library/Application Support/Echos/config.json`) is written atomically using a write-then-rename swap mechanism, preventing data corruption during unexpected shutdowns.

---

## 💻 Developer Setup

Want to contribute or build from source? 

```bash
# 1. Clone the repository
git clone https://github.com/Akoirala47/Echos.git
cd Echos

# 2. Install libsndfile (Required for PortAudio on macOS)
brew install libsndfile

# 3. Create a Python 3.11 virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 5. Run the application
python -m echos.main
```

### Running Tests

Echos is tested via `pytest` focusing on configurations, core logic, and utilities (no GUI event loops required).

```bash
pytest tests/ -v
```

### Packaging the macOS DMG

Echos bundles all Python runtimes and frameworks (including a natively patched PortAudio) via `py2app` and `create-dmg`. 

```bash
brew install create-dmg
chmod +x build/build.sh
./build/build.sh
```

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

*Optimized for privacy, built for learning. Take back your focus with Echos.*