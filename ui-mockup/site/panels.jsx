// Transcript + Notes panels.

const SAMPLE_TRANSCRIPT = `Okay, so today we're going to pick up where we left off with dynamic programming. Last lecture we did the standard top-down memoization formulation, and what I want to do today is contrast that with the bottom-up tabular approach and start to develop some intuition for when each one is the right tool.

The classic motivating example is, of course, longest common subsequence. Let me set it up: we have two strings, X of length m and Y of length n. We want to find the longest sequence of characters that appears in both as a subsequence — not a substring, a subsequence — meaning the characters appear in order but not necessarily contiguously.

The recurrence — and I'll write it on the board — is: if X[i] equals Y[j], then LCS of i, j is 1 plus LCS of i minus one, j minus one. Otherwise, it's the max of LCS of i minus one, j and LCS of i, j minus one.

Now, the key insight for the tabular approach is that when we fill in the DP table…`;

const SAMPLE_NOTES_MD = `# CS446 · Lecture 5
*April 24, 2026*

## Dynamic Programming — Top-Down vs Bottom-Up

Today's contrast: **memoization** (top-down) vs **tabulation** (bottom-up). Goal is to develop intuition for when each is the right tool.

### Motivating Example: Longest Common Subsequence

- Inputs: two strings **X** (length *m*) and **Y** (length *n*)
- Find the longest **subsequence** (not substring) appearing in both
  - Characters in order, **not** necessarily contiguous

#### Recurrence

\`\`\`
LCS(i, j) =
  1 + LCS(i-1, j-1)            if X[i] == Y[j]
  max(LCS(i-1, j), LCS(i, j-1)) otherwise
\`\`\`

### Tabular (Bottom-Up) Approach

- Fill a 2D table of size (m+1) × (n+1)
- Iterate row by row, left to right
- Each cell only depends on the cell above, to the left, and diagonally above-left
- Time complexity: **O(mn)**, space: **O(mn)** (reducible to O(min(m,n)))

## Key Takeaways

- Top-down is easier to write; bottom-up has lower constant factors and avoids stack overflow
- Always identify the recurrence first, table layout second
- Watch for state-compression opportunities once the table is correct`;

function renderMarkdown(md) {
  // Lightweight md → html for the prototype — handles the subset we use.
  const lines = md.split('\n');
  let html = '';
  let inCode = false;
  let inList = false;
  for (let raw of lines) {
    if (raw.startsWith('```')) {
      if (inCode) { html += '</code></pre>'; inCode = false; }
      else { html += '<pre><code>'; inCode = true; }
      continue;
    }
    if (inCode) { html += escapeHtml(raw) + '\n'; continue; }
    let line = raw;
    line = escapeHtml(line);
    line = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    line = line.replace(/\*(.+?)\*/g, '<em>$1</em>');
    line = line.replace(/`(.+?)`/g, '<code>$1</code>');
    if (line.startsWith('#### ')) html += `<h4>${line.slice(5)}</h4>`;
    else if (line.startsWith('### ')) html += `<h3>${line.slice(4)}</h3>`;
    else if (line.startsWith('## ')) html += `<h2>${line.slice(3)}</h2>`;
    else if (line.startsWith('# ')) html += `<h1>${line.slice(2)}</h1>`;
    else if (line.startsWith('- ')) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${line.slice(2)}</li>`;
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      if (line.trim() === '') html += '';
      else html += `<p>${line}</p>`;
    }
  }
  if (inList) html += '</ul>';
  if (inCode) html += '</code></pre>';
  return html;
}
function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function PanelHeader({ label, right }) {
  return (
    <div style={{
      height: 32,
      padding: '0 12px',
      display: 'flex', alignItems: 'center', gap: 6,
      borderBottom: '1px solid var(--border-soft)',
      fontSize: 10, fontWeight: 700, letterSpacing: 0.8,
      color: 'var(--text-faint)', textTransform: 'uppercase',
      flexShrink: 0,
    }}>
      {label}
      <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 4 }}>{right}</span>
    </div>
  );
}

function MiniBtn({ children, onClick, ghost, primary }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: primary ? 'var(--text)' : (ghost ? 'transparent' : '#fff'),
        color: primary ? '#fff' : 'var(--text-muted)',
        border: ghost ? 'none' : `1px solid var(--border-soft)`,
        borderRadius: 4,
        fontSize: 10.5, fontWeight: 500,
        padding: '3px 8px',
        textTransform: 'uppercase', letterSpacing: 0.5,
      }}
    >{children}</button>
  );
}

function TranscriptPanel({ text, setText, state }) {
  const empty = !text;
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--panel-bg)', minWidth: 0, borderRight: '1px solid var(--border-soft)' }}>
      <PanelHeader label="Live Transcript" right={
        <>
          <MiniBtn ghost onClick={() => setText('')}>Clear</MiniBtn>
          <MiniBtn ghost>Export .txt</MiniBtn>
        </>
      } />
      <div style={{ flex: 1, overflow: 'auto', padding: '14px 18px' }} className="scroll">
        {empty ? (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, lineHeight: 1.6 }}>
            {state === 'idle' ? 'Press Start Recording to begin. The live transcript will appear here as you speak.' : 'Listening…'}
          </div>
        ) : (
          <div style={{ fontSize: 13.5, lineHeight: 1.7, color: 'var(--text)', whiteSpace: 'pre-wrap', fontFamily: 'Inter, sans-serif' }}>
            {text}
            {(state === 'recording') && <span style={{ display: 'inline-block', width: 7, height: 14, background: 'var(--accent)', verticalAlign: 'middle', marginLeft: 2, animation: 'pulse-rec 1s ease-in-out infinite' }} />}
          </div>
        )}
      </div>
    </div>
  );
}

function NotesPanel({ notes, state, onGenerate, onRegenerate }) {
  const [view, setView] = React.useState('preview');
  const canGenerate = state === 'stopped';
  const empty = !notes;
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--panel-bg)', minWidth: 0 }}>
      <PanelHeader label="Structured Notes" right={
        <>
          <MiniBtn ghost>Copy</MiniBtn>
          <MiniBtn ghost onClick={() => setView(v => v === 'preview' ? 'raw' : 'preview')}>{view === 'preview' ? 'Raw' : 'Preview'}</MiniBtn>
        </>
      } />
      <div style={{ flex: 1, overflow: 'auto', padding: '14px 22px' }} className="scroll">
        {empty ? (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, lineHeight: 1.6 }}>
            {state === 'stopped' ? 'Click Generate Notes to convert the transcript into structured Markdown.' : 'Notes appear here once the session is complete.'}
          </div>
        ) : (
          view === 'preview'
            ? <div className="md-preview" style={mdPreviewStyle} dangerouslySetInnerHTML={{ __html: renderMarkdown(notes) }} />
            : <pre style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{notes}</pre>
        )}
      </div>
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid var(--border-soft)',
        display: 'flex', gap: 8, alignItems: 'center',
      }}>
        <button
          onClick={onGenerate}
          disabled={!canGenerate}
          style={{
            padding: '7px 14px',
            background: canGenerate ? 'var(--text)' : 'var(--border-soft)',
            color: canGenerate ? '#fff' : 'var(--text-faint)',
            border: 'none', borderRadius: 6,
            fontSize: 12.5, fontWeight: 600,
            cursor: canGenerate ? 'pointer' : 'not-allowed',
          }}
        >Generate Notes</button>
        <button
          onClick={onRegenerate}
          disabled={!notes}
          style={{
            padding: '7px 12px',
            background: 'transparent',
            color: notes ? 'var(--text-muted)' : 'var(--text-faint)',
            border: '1px solid var(--border-soft)', borderRadius: 6,
            fontSize: 12, fontWeight: 500,
            cursor: notes ? 'pointer' : 'not-allowed',
          }}
        >Regenerate…</button>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-faint)' }}>
          gemma-4-31b · streaming
        </span>
      </div>
    </div>
  );
}

const mdPreviewStyle = {
  fontSize: 13, lineHeight: 1.65, color: 'var(--text)',
};

// inject style for .md-preview content
(function () {
  const css = `
.md-preview h1 { font-size: 18px; font-weight: 700; margin: 4px 0 6px; }
.md-preview h2 { font-size: 14.5px; font-weight: 700; margin: 14px 0 4px; padding-left: 8px; border-left: 3px solid var(--accent); }
.md-preview h3 { font-size: 13px; font-weight: 600; margin: 10px 0 3px; }
.md-preview h4 { font-size: 12px; font-weight: 600; margin: 8px 0 3px; color: var(--text-muted); }
.md-preview p { margin: 4px 0 6px; }
.md-preview ul { padding-left: 20px; margin: 4px 0 6px; }
.md-preview li { margin: 2px 0; }
.md-preview em { color: var(--text-muted); font-style: italic; }
.md-preview strong { font-weight: 600; }
.md-preview code { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; background: #f4f1ea; padding: 1px 5px; border-radius: 3px; border: 1px solid var(--border-soft); }
.md-preview pre { background: #f6f3ec; border: 1px solid var(--border-soft); border-radius: 5px; padding: 10px 12px; overflow: auto; }
.md-preview pre code { background: none; border: none; padding: 0; font-size: 11.5px; }
`;
  const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
})();

function StatusBar({ state, vaultPath, onSave, onOpen, onEndSession, onNewSession, savedFilename, endSessionPlacement }) {
  const showEndSession = (state === 'recording' || state === 'paused') && endSessionPlacement === 'statusbar';
  const showSave = state === 'notes_done' || state === 'saved';
  const showOpen = state === 'saved';
  const showNew = state === 'stopped' || state === 'notes_done' || state === 'saved';

  let statusText = STATE_LABELS[state]?.label || 'Ready';
  if (state === 'saved' && savedFilename) statusText = `Saved · ${savedFilename}`;

  return (
    <div style={{
      height: 30,
      padding: '0 12px',
      background: 'var(--statusbar-bg)',
      borderTop: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', gap: 10,
      fontSize: 11.5,
      flexShrink: 0,
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: STATE_LABELS[state]?.dot || 'var(--text-faint)',
        animation: state === 'recording' ? 'pulse-rec 1.2s ease-in-out infinite' : 'none',
      }} />
      <span style={{ color: 'var(--text-muted)' }}>{statusText}</span>
      <span style={{ color: 'var(--text-faint)' }}>·</span>
      <span style={{ color: 'var(--text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{vaultPath}</span>

      <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6 }}>
        {showEndSession && (
          <button onClick={onEndSession} title="End the current session — finalises the file. (⌘⇧E)" style={statusGhostBtn}>
            ■ End Session
          </button>
        )}
        {showNew && (
          <button onClick={onNewSession} style={statusGhostBtn}>＋ New Session</button>
        )}
        {showOpen && (
          <button onClick={onOpen} style={statusGhostBtn}>Open in Obsidian</button>
        )}
        {showSave && (
          <button onClick={onSave} style={{
            ...statusGhostBtn,
            background: state === 'saved' ? 'var(--ready)' : 'var(--text)',
            color: '#fff', borderColor: 'transparent',
          }}>
            {state === 'saved' ? '✓ Saved' : 'Save to Obsidian'}
          </button>
        )}
      </span>
    </div>
  );
}

const statusGhostBtn = {
  background: 'transparent',
  border: '1px solid var(--border)',
  color: 'var(--text-muted)',
  padding: '3px 10px',
  height: 22,
  borderRadius: 4,
  fontSize: 11, fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 4,
};

Object.assign(window, { TranscriptPanel, NotesPanel, StatusBar, SAMPLE_TRANSCRIPT, SAMPLE_NOTES_MD });
