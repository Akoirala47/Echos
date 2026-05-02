### 1. Graph Canvas (Obsidian-Style WebGL Architecture)

Your previous PyQt6 graph rendering failed because DOM-based or native widget-based rendering chokes past a few hundred nodes. Obsidian solves this by using **WebGL for rendering** and **Web Workers for physics**, keeping the main UI thread completely free.

**Technical Implementation:**
* **Host:** `QWebEngineView` loading a local HTML page.
* **Renderer:** PIXI.js (2D WebGL). This is what allows Obsidian to render thousands of nodes at 60fps. You draw nodes as WebGL primitives (circles/lines) rather than DOM elements.
* **Physics Engine:** A force-directed graph library (like `d3-force` or `ngraph.forcelayout`) running inside a **Web Worker**. The worker calculates the x/y positions in the background and posts arrays of coordinates back to the main JS thread on every tick. PIXI.js just paints those coordinates.
* **Communication:** Use `QWebChannel` to pass click events from the JavaScript canvas back to PyQt to open the corresponding file tab.

**Visuals & Theme Constraints:**
* **Background:** `<canvas>` background set strictly to `CANVAS_BG = "#1c1b17"`. No grid or gravity wells. It is an open, flat space showing all nodes.
* **Nodes:** Base fill uses a `PANEL_BG` tint. 
* **Edges:** Drawn as straight WebGL lines (not bezier, for performance) drawing from `ACCENT` (strong connections) fading to `BORDER` (weak connections).
* **Overlay UI:** Toolbar/search filters float over the canvas using standard HTML/CSS, styled with `WINDOW_BG` and `TEXT_FAINT` per your token system. 

### 2. The Fingerprint System (Context-Preserving)

The core mechanic remains exactly as established to prevent blowing up the LLM context window.

**Data Structure (YAML Frontmatter):**
```yaml
fingerprint: "concepts:[rl-training,reward-shaping] | domain:[ml] | hash:a3f9"
```

**The Pipeline:**
1.  **Local Pre-filter (Vector Embedding):** Run a lightweight local model (e.g., `all-MiniLM-L6-v2`) against the new note's `concepts` string. This generates a 384-dimensional float vector. Given Apple Silicon's unified memory architecture, this runs locally in milliseconds.
2.  **Similarity Search:** Perform a cosine similarity search against the SQLite database of all stored vectors. Retrieve the top 20 candidate fingerprints.
3.  **LLM Processing:** Pass only the new note's content and the 20 candidate fingerprints to the LLM (totaling ~2k-4k tokens). 
4.  **Output:** The LLM mints the new note's fingerprint (reusing existing concept vocabulary where possible) and outputs the specific edge connections and connection strengths.

### 3. SQLite Indexing Engine (The Mechanical Core)

The index operates asynchronously to keep the editor responsive.

**Database Schema (`.echoes/vault.index.db`):**
* **`notes`**: `(id, path, modified_at, content_hash, fingerprint_text, vector_blob, dirty)`
* **`edges`**: `(source_id, target_id, strength, reason, created_at)`
* **`tags`**: `(note_id, tag, source)`

**Execution Mechanics:**
* **Watchdog Thread:** Python `watchdog` monitors the `.echoes` directory. On file save, it flips `dirty=1` for that file's row in the `notes` table.
* **Debounced Async Execution:** The actual re-indexing does not happen on save. A background thread waits for a 30-second debounce window after the last edit to a note. 
* **Batch Processing:** Once the debounce fires, the system groups all `dirty=1` files, runs the local embedding, and batches the LLM fingerprint assignment.
* **Graph Update:** The background thread writes the new edges to SQLite and sends a JSON payload via `QWebChannel` to the PIXI.js canvas to instantly update the graph visuals without a full reload.