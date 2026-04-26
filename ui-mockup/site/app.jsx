// Main app — wires everything together with the new state machine.

const ACCENT_PAIRS = {
  'amber-rose':   { primary: '#c2410c', secondary: '#be185d' },
  'indigo-teal':  { primary: '#4338ca', secondary: '#0d9488' },
  'forest-clay':  { primary: '#166534', secondary: '#9a3412' },
};

function applyAccent(pair) {
  const css = ACCENT_PAIRS[pair] || ACCENT_PAIRS['amber-rose'];
  document.documentElement.style.setProperty('--accent', css.primary);
  document.documentElement.style.setProperty('--accent-2', css.secondary);
  document.documentElement.style.setProperty('--selected', css.primary + '1A');
  document.documentElement.style.setProperty('--selected-strong', css.primary + '2D');
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentPair": "amber-rose",
  "photoShape": "circle",
  "density": "regular",
  "endSessionPlacement": "statusbar",
  "sidebarMode": "tree+topics"
}/*EDITMODE-END*/;

function ConfirmDialog({ title, body, confirmLabel, cancelLabel, danger, onConfirm, onCancel }) {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: 'rgba(0,0,0,0.18)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 50,
      animation: 'fade-in 160ms ease both',
    }}>
      <div style={{
        width: 380,
        background: 'var(--window-bg)',
        borderRadius: 10,
        boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        border: '1px solid var(--border)',
        padding: '20px 22px 16px',
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{title}</div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 16 }}>{body}</div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onCancel} style={{
            padding: '6px 14px', height: 28,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text)', borderRadius: 5,
            fontSize: 12, fontWeight: 500,
          }}>{cancelLabel || 'Cancel'}</button>
          <button onClick={onConfirm} style={{
            padding: '6px 14px', height: 28,
            background: danger ? 'var(--recording)' : 'var(--text)',
            color: '#fff', border: 'none', borderRadius: 5,
            fontSize: 12, fontWeight: 600,
          }}>{confirmLabel || 'OK'}</button>
        </div>
      </div>
    </div>
  );
}

function TitleBar() {
  return (
    <div style={{
      height: 36,
      background: 'linear-gradient(to bottom, #f1efe8, #e9e7df)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      padding: '0 12px',
      flexShrink: 0,
      position: 'relative',
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f57', border: '0.5px solid rgba(0,0,0,0.1)' }} />
        <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#febc2e', border: '0.5px solid rgba(0,0,0,0.1)' }} />
        <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#28c840', border: '0.5px solid rgba(0,0,0,0.1)' }} />
      </div>
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 0, bottom: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)',
        pointerEvents: 'none',
      }}>
        Echos — CS446 — Algorithms
      </div>
    </div>
  );
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  React.useEffect(() => { applyAccent(tweaks.accentPair); }, [tweaks.accentPair]);

  // App state machine
  const [state, setState] = React.useState('idle'); // idle, recording, paused, stopped, generating, notes_done, saved
  const [elapsed, setElapsed] = React.useState(0);
  const [sessionNum, setSessionNum] = React.useState(5);
  const [transcript, setTranscript] = React.useState('');
  const [notes, setNotes] = React.useState('');
  const [savedFilename, setSavedFilename] = React.useState(null);
  const [confirmEnd, setConfirmEnd] = React.useState(false);
  const [activeTopic, setActiveTopic] = React.useState('t1');
  const [target, setTarget] = React.useState('School/CS446 — Algorithms/Lectures');

  const activeTopicObj = TOPICS_DATA.find(t => t.id === activeTopic);
  const courseName = activeTopicObj ? activeTopicObj.name : 'No topic';
  const accentColor = activeTopicObj ? activeTopicObj.color : 'var(--accent)';
  const breadcrumb = target.split('/');

  // Elapsed timer
  React.useEffect(() => {
    if (state !== 'recording') return;
    const id = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(id);
  }, [state]);

  // Live transcript simulation
  React.useEffect(() => {
    if (state !== 'recording') return;
    let i = transcript.length;
    const id = setInterval(() => {
      if (i >= SAMPLE_TRANSCRIPT.length) return;
      const next = SAMPLE_TRANSCRIPT.slice(0, i + 4);
      setTranscript(next);
      i = next.length;
    }, 80);
    return () => clearInterval(id);
  }, [state]);

  // Notes streaming simulation
  const streamNotes = () => {
    setState('generating');
    setNotes('');
    let i = 0;
    const id = setInterval(() => {
      if (i >= SAMPLE_NOTES_MD.length) {
        clearInterval(id);
        setState('notes_done');
        return;
      }
      i = Math.min(SAMPLE_NOTES_MD.length, i + 14);
      setNotes(SAMPLE_NOTES_MD.slice(0, i));
    }, 30);
  };

  const onPrimary = () => {
    if (state === 'idle') {
      setState('recording');
      setElapsed(0);
      setTranscript('');
      setNotes('');
      setSavedFilename(null);
    } else if (state === 'recording') {
      setState('paused');
    } else if (state === 'paused') {
      setState('recording');
    } else {
      // stopped → start a fresh session (no confirm — STOPPED is already terminal)
      setState('idle');
      setElapsed(0);
      setTranscript('');
      setNotes('');
      setSavedFilename(null);
      setSessionNum(s => s + 1);
    }
  };

  const onEndSession = () => setConfirmEnd(true);
  const onConfirmEnd = () => {
    setConfirmEnd(false);
    setState('stopped');
  };

  const onNewSession = () => {
    setState('idle');
    setElapsed(0);
    setTranscript('');
    setNotes('');
    setSavedFilename(null);
    setSessionNum(s => s + 1);
  };

  const onSave = () => {
    const fname = `Lecture-${String(sessionNum).padStart(2, '0')}.md`;
    setSavedFilename(fname);
    setState('saved');
  };

  const onRecordHere = (path) => {
    setTarget(path);
    setActiveTopic(null);
  };

  // keyboard
  React.useEffect(() => {
    const onKey = (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === 'r' && !e.shiftKey) {
        e.preventDefault();
        if (state === 'idle' || state === 'paused') onPrimary();
      } else if (meta && e.key === 'p' && !e.shiftKey) {
        e.preventDefault();
        if (state === 'recording') onPrimary();
      } else if (meta && e.shiftKey && (e.key === 'E' || e.key === 'e')) {
        e.preventDefault();
        if (state === 'recording' || state === 'paused') onEndSession();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [state]);

  return (
    <div style={{
      width: 1220, height: 820,
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: 'var(--shadow-window)',
      background: 'var(--window-bg)',
      display: 'flex', flexDirection: 'column',
      position: 'relative',
    }}>
      <TitleBar />
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <Sidebar
          target={target}
          setTarget={setTarget}
          activeTopic={activeTopic}
          setActiveTopic={setActiveTopic}
          onRecordHere={onRecordHere}
          accent={accentColor}
          photoShape={tweaks.photoShape}
          density={tweaks.density}
          sidebarMode={tweaks.sidebarMode}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <RecordBar
            state={state}
            elapsed={elapsed}
            sessionNum={sessionNum}
            setSessionNum={setSessionNum}
            onPrimary={onPrimary}
            courseName={courseName}
            breadcrumb={breadcrumb}
            accentColor={accentColor}
          />
          <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
            <TranscriptPanel text={transcript} setText={setTranscript} state={state} />
            <NotesPanel notes={notes} state={state} onGenerate={streamNotes} onRegenerate={streamNotes} />
          </div>
        </div>
      </div>
      <StatusBar
        state={state}
        vaultPath="~/Obsidian/my-vault"
        onSave={onSave}
        onOpen={() => {}}
        onEndSession={onEndSession}
        onNewSession={onNewSession}
        savedFilename={savedFilename}
        endSessionPlacement={tweaks.endSessionPlacement}
      />

      {confirmEnd && (
        <ConfirmDialog
          title="End this session?"
          body="You won't be able to add more audio to this lecture. Pause instead if you only need a short break — pausing keeps the session open."
          confirmLabel="End Session"
          cancelLabel="Keep Recording"
          danger
          onConfirm={onConfirmEnd}
          onCancel={() => setConfirmEnd(false)}
        />
      )}

      <TweaksPanel title="Tweaks">
        <TweakSection title="Recording UX">
          <TweakRadio
            label="End Session button"
            value={tweaks.endSessionPlacement}
            onChange={(v) => setTweak('endSessionPlacement', v)}
            options={[
              { value: 'statusbar', label: 'Status bar' },
              { value: 'menu-only', label: 'Menu only' },
            ]}
          />
        </TweakSection>
        <TweakSection title="Sidebar">
          <TweakRadio
            label="Layout"
            value={tweaks.sidebarMode}
            onChange={(v) => setTweak('sidebarMode', v)}
            options={[
              { value: 'tree+topics', label: 'Tree + Topics' },
              { value: 'vault-only',  label: 'Vault only' },
              { value: 'topics-only', label: 'Topics only' },
            ]}
          />
          <TweakRadio
            label="Topic dot shape"
            value={tweaks.photoShape}
            onChange={(v) => setTweak('photoShape', v)}
            options={[
              { value: 'circle', label: 'Circle' },
              { value: 'square', label: 'Square' },
            ]}
          />
          <TweakRadio
            label="Density"
            value={tweaks.density}
            onChange={(v) => setTweak('density', v)}
            options={[
              { value: 'regular', label: 'Regular' },
              { value: 'compact', label: 'Compact' },
            ]}
          />
        </TweakSection>
        <TweakSection title="Accent">
          <TweakRadio
            label="Accent pair"
            value={tweaks.accentPair}
            onChange={(v) => setTweak('accentPair', v)}
            options={[
              { value: 'amber-rose',  label: 'Amber/Rose' },
              { value: 'indigo-teal', label: 'Indigo/Teal' },
              { value: 'forest-clay', label: 'Forest/Clay' },
            ]}
          />
        </TweakSection>
        <TweakSection title="Demo">
          <TweakButton onClick={() => { /* jump to recording */ if (state === 'idle') { setState('recording'); setElapsed(0); setTranscript(''); }}}>
            ► Start a session
          </TweakButton>
          <TweakButton onClick={() => setState('stopped')}>
            Skip to “session complete”
          </TweakButton>
          <TweakButton onClick={() => { setNotes(SAMPLE_NOTES_MD); setState('notes_done'); }}>
            Skip to “notes ready”
          </TweakButton>
          <TweakButton onClick={() => { setState('idle'); setTranscript(''); setNotes(''); setElapsed(0); setSavedFilename(null); }}>
            ↺ Reset
          </TweakButton>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
