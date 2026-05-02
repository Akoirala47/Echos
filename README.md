# Echos

**Local AI transcription, lecture notes, and vault knowledge graph for macOS**

**Echos** is a native macOS app that captures microphone audio, transcribes it **on-device** with **Whisper large-v3** (PyTorch / MPS), and uses **Google’s Gemini models** (default **Gemma 4 31B** via [Google AI Studio](https://aistudio.google.com)) to turn transcripts into structured Markdown. Notes are saved into an **Obsidian** vault—with optional **YAML front matter**, including a compact **concept fingerprint** for later graph linking.

Privacy boundary: **raw audio stays on your Mac.** Only text is sent to Google when you generate or draft notes.

---

## Features & benefits

- **Local transcription** — **Whisper large-v3** on Apple Silicon (Metal / MPS) when available; falls back to CPU on Intel machines.
- **Obsidian-aware workflow** — Course-based folders, YAML front matter, “Open in Obsidian,” vault URI support. Sidebar tree stays in sync with disk via **`QFileSystemWatcher`** (hidden folders such as `.obsidian` are ignored).
- **Incremental note drafting** — While recording, once enough **new transcript** has accumulated (~3 500 characters per chunk), Echos can **stream drafted notes** in the Notes panel so you are not stuck with a blank page until the session ends (requires a configured API key).
- **Manual generate & regenerate** — After **End Session**, use **Generate Notes** and **Regenerate…** with custom instructions; thinking/reasoning tags from the model are stripped before display.
- **Brain View (knowledge graph)** — **`View → Brain View` (⌘G)** opens **`echos/assets/graph.html`**: **PIXI.js** draws nodes on **WebGL**, **`d3-force`** runs the physics, and **`qwebchannel.js`** with **`QtWebChannel`** pushes graph JSON from Python and receives clicks. Layered edges reflect **wikilinks**, overlapping **fingerprint concepts**, and high **embedding cosine** similarity. **`View → Command Palette` (⇧⌘P)** jumps to vault files or common actions.
- **Vault index (`SQLite`)** — Under your vault root, **`.echoes/vault.index.db`** stores indexed notes (`vector_blob`, `fingerprint_text`, `dirty`), **edges**, and **tags**. The watcher marks changed `.md` files dirty immediately; indexing runs **after a 30 s quiet debounce** of saves so bursts of edits collapse into one batch.
- **Fingerprints & embeddings** — **FingerprintEngine** calls the configured **Google AI** (`google-genai`) model for structured concepts/domains (`concepts:[…] | domain:[…] | hash:…`, kept short for YAML). When the vault grows past ~30 fingerprinted notes, **`top_k_similar`** narrows vocabulary candidates (~20 neighbours) via **`all-MiniLM-L6-v2`** embeddings. **`sentence-transformers`** persists **384‑dim** vectors in SQLite for cosine-based graph edges (see **`ConnectionResolver`**).
- **Sessions** — Pause / resume recording, overlapping chunk dedupe in the transcription path, Dock recording indicator optional, option to prevent sleep during capture.
- **Editor tabs** — **`SplitTabArea`** layers the Echoes workspace with Markdown editor tabs; clicking a Brain View node opens that vault path via **`TabManager.open_file`** and returns you to the recorder layout (**`AppController`**).
- **In-app updates** — On launch, Echos may check **`Akoirala47/Echos`** GitHub releases and offer to download the latest `.dmg`.

---

## Requirements

| Requirement  | Details |
| ------------- | ------- |
| **macOS**    | **13 Ventura** or later. |
| **Hardware** | **Apple Silicon** strongly recommended for responsive Whisper inference. Intel Macs use CPU (slower but supported). Extra RAM helps when Whisper, embeddings, and Brain View (WebGL) are active together. |
| **Obsidian** | [Obsidian](https://obsidian.md) recommended; Echos writes into folders you designate inside a vault structure. |
| **API key**  | **Google AI API key** ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) for note generation & fingerprint passes during indexing. |
| **Storage**    | Roughly **4 GB** free for the app plus Whisper (~3 GB downloaded on first use). The embedding model pulls in separately the first time `sentence-transformers` runs. |
| **Brain View host** | Visualization is **`echos/assets/graph.html`** (**vendor PIXI + d3**, WebGL sprites + force simulation). **`GraphCanvasWidget`** (`echos/ui/graph_canvas.py`) hosts that page inside Qt **`QWebEngineView`** (Chromium) and drives **`qtwebchannel`** ↔ **`QtWebChannel`** so Python can **`runJavaScript`** updates and receive node clicks. Without WebEngine/Chromium payloads available to the process, **`GraphCanvasWidget`** falls back to its placeholder label. |

---

## Installation

1. Download the latest **`Echos-*.dmg`** from the [Releases](https://github.com/Akoirala47/Echos/releases) page (version in source: `echos/version.py`).
2. Open the DMG and drag **Echos.app** into **Applications**.
3. Launch from Launchpad or Spotlight.

> **Gatekeeper:** Builds may lack full Apple notarisation. On first launch, use **Right‑click → Open** if macOS warns about an unidentified developer.

---

## Getting started

A short onboarding wizard appears on **first launch** if no config exists.

1. **Welcome** — Overview of microphone and file access.
2. **Configure** — Pick your vault root and paste your **Google AI** key (validated in the wizard).
3. **Model download** — Whisper **large‑v3** is fetched into **`~/.cache/huggingface/hub/`** (Hugging Face cache). You can dismiss the wizard; partial downloads resume on next launch.

Config is stored atomically under **`~/Library/Application Support/Echos/config.json`** (write-temp-then-rename). Logs rotate under **`~/Library/Logs/Echos/echos.log`**.

---

## Interface & usage

### Sidebar — courses & vault tree

- **Courses**: Named topics mapped to vault subfolders, colors, reorder, next **lecture number** auto-detection.
- **Live tree**: Mirrors `.md` files and folders under the vault (excluding dot-folders).

### Echoes workspace (recording + panels)

- **Record bar**: Waveform RMS visualization (optional); **⌘R** start/stop style shortcuts wired from the menus.
- **Transcript**: Live Whisper chunks (default **~6 s** chunks — tune in Settings); editable text.
- **Notes**: Markdown preview / raw toggle; streamed output during drafting or explicit generation.

### Brain View & command palette

- **⌘G** — Opens the stacked **Brain View** graph page; **`load_graph`** is fed JSON from **`ConnectionResolver.resolve(VaultIndex)`** after **`IndexWorker`** finishes.
- **⇧⌘P** — Command palette for quick vault navigation and a few bundled actions.

### Saving to Obsidian

**⌘S** (**Save Note**) merges **Markdown · inject_frontmatter(...)**: `course`, `lecture`, `date`, `tags`, `echos_version`, optional **`fingerprint`** string from generation when available.

---

## Settings

Open **Echos → Settings… (⌘,)**.

| Area | Highlights |
| ---- | ----------- |
| **Audio / ASR** | Chunk length (3–10 s), overlap (0–1 s), **Auto / MPS / CPU** device. |
| **Notes LLM** | Model id (default aligns with **`gemma-4-31b-it`** in config defaults), temperature, max tokens, output language. |
| **YAML** | Toggle front matter include; customise tag template (`{course_lower}` placeholder). |

---

## Architecture (developer mental model)

| Layer | Role |
| ----- | ----- |
| **`main.py`** | Dylib patching for **`sounddevice` / `soundfile`** in bundles, **`Fusion`** styling, palette, onboarding gate, **`AppController`**. |
| **`AppController`** | State machine (**IDLE**, **RECORDING**, **GENERATING**, etc.), wires **`AudioWorker`**, **`NotesWorker`**, **`ModelDownloadWorker`**, indexing, updates, shortcuts. |
| **`ModelManager`** | Whisper HF id **`openai/whisper-large-v3`**, device selection, progressive download + load. |
| **`AudioWorker`** | **`sounddevice`** stream on **`QThread`**, numpy buffers → transcription queue. |
| **`NotesWorker`** | Streaming **`google-genai`** completions; `_strip_thinking` cleanup. |
| **`VaultWatcher`** | **`QFileSystemWatcher`** + **30 s** debounce **`reindex_ready`** when connected to **`VaultIndex`**. |
| **`VaultIndex`** | **`sqlite3`** at **`<vault>/.echoes/vault.index.db`**. |
| **`IndexWorker`** | Per dirty note: **`EmbeddingEngine.embed`**, **`FingerprintEngine.generate`**, `[[wikilink]]` extraction into the edges table, clears **`dirty`**. |
| **`ConnectionResolver`** | Turns the latest **`VaultIndex`** snapshot into graph payload: **wikilink edges first**, then **concept-overlap** strengths from fingerprints, then **cosine ≥ 0.8** vector pairs. |
| **`GraphCanvasWidget`** | Best-effort **`QtWebEngineWidgets`**: **`echosGraphBridge`** (**`QObject`**) registered on **`QtWebChannel`**, **`graph.html`** (PIXI + d3-force), **`runJavaScript`** invokes **`window.echosGraph.loadGraph`** with **`ConnectionResolver`** JSON. Fallback **`QLabel`** when WebEngine import fails. |

---

## Developer setup

```bash
git clone https://github.com/Akoirala47/Echos.git
cd Echos

brew install libsndfile   # dev machines without wheel-bundled audio libs may need this

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Brain View shells graph.html in Qt WebEngine (Chromium). requirements.txt pulls PyQt6-WebEngine (+ PyQt6).

python -m echos.main
```

### Tests

```bash
pytest tests/ -v
```

pytest covers **`vault_index`**, **`fingerprint`**, **`index_worker`**, **`connection_resolver`**, **`vault_watcher`**, **`graph_canvas`**, **`config_manager`**, Markdown helpers, **`tab_manager`**, **`obsidian_manager`**, **`model_manager`**, **`audio_utils`**, **`frontmatter`**, and related pieces (no requirement to run headless GUI workflows for every scenario).

### Packaging a macOS DMG

Uses **`py2app`** helpers under **`build/`**.

```bash
brew install create-dmg
chmod +x build/build.sh
./build/build.sh
```

---

## Related docs

- **`SPEC.md`** — Product/spec alignment (historical branding *Scout* in the title; codebase name is **Echos**).
- **`graph-fingerprinting-outline.md`** — Design notes for WebGPU-style graph sizing and fingerprint pipeline details.

---

## License

MIT — see **`LICENSE`**.
