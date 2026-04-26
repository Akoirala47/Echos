// Record bar — the new "Pause-only primary control" pattern.
// Primary button never says "Stop". End Session lives in the status bar / menu.

const STATE_LABELS = {
  idle: { dot: 'var(--text-faint)', label: 'Ready' },
  recording: { dot: 'var(--recording)', label: 'Recording' },
  paused: { dot: 'var(--paused)', label: 'Paused' },
  stopped: { dot: 'var(--text-faint)', label: 'Session complete' },
  generating: { dot: '#2563eb', label: 'Generating notes…' },
  notes_done: { dot: 'var(--ready)', label: 'Notes ready' },
  saved: { dot: 'var(--ready)', label: 'Saved' },
};

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function Waveform({ active, paused }) {
  const bars = 36;
  const arr = React.useMemo(() => Array.from({ length: bars }, (_, i) => ({ i, delay: (i * 73) % 900 })), []);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 2.5,
      height: 28, flex: 1, minWidth: 120,
      opacity: paused ? 0.4 : 1,
      transition: 'opacity 200ms ease',
    }}>
      {arr.map(({ i, delay }) => {
        const baseH = 4 + ((i * 17) % 18);
        return (
          <div key={i} style={{
            width: 2.5, height: baseH,
            background: active && !paused ? 'var(--accent)' : 'var(--text-faint)',
            borderRadius: 2,
            transformOrigin: 'center',
            animation: active && !paused ? `wave 1.05s ease-in-out ${delay}ms infinite` : 'none',
            opacity: active ? 0.85 : 0.45,
          }} />
        );
      })}
    </div>
  );
}

// Primary button — Start / Pause / Resume.  Never "Stop."
function PrimaryButton({ state, onClick }) {
  let label, icon, bg, fg, border, glow;
  if (state === 'idle') {
    label = 'Start Recording';
    icon = <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: '#fff' }} />;
    bg = 'var(--recording)'; fg = '#fff'; border = 'transparent';
  } else if (state === 'recording') {
    label = 'Pause';
    icon = <span style={{ display: 'inline-flex', gap: 3 }}><i style={{ width: 3, height: 11, background: '#fff', borderRadius: 1 }} /><i style={{ width: 3, height: 11, background: '#fff', borderRadius: 1 }} /></span>;
    bg = 'var(--paused)'; fg = '#fff'; border = 'transparent';
  } else if (state === 'paused') {
    label = 'Resume';
    icon = <span style={{ display: 'inline-block', width: 0, height: 0, borderLeft: '9px solid #fff', borderTop: '6px solid transparent', borderBottom: '6px solid transparent' }} />;
    bg = 'var(--ready)'; fg = '#fff'; border = 'transparent';
  } else {
    // stopped / others — primary becomes "Start New Session"
    label = 'Start New Session';
    icon = <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: 'var(--recording)' }} />;
    bg = '#fff'; fg = 'var(--text)'; border = 'var(--border)';
  }
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 9,
        padding: '0 18px', height: 38,
        background: bg, color: fg,
        border: `1px solid ${border}`,
        borderRadius: 8,
        fontSize: 13.5, fontWeight: 600,
        boxShadow: state === 'recording' ? '0 0 0 0 rgba(217,47,47,0)' : '0 1px 2px rgba(0,0,0,0.06)',
        transition: 'background 140ms ease, transform 80ms ease',
      }}
      onMouseDown={(e) => e.currentTarget.style.transform = 'translateY(1px)'}
      onMouseUp={(e) => e.currentTarget.style.transform = 'none'}
      onMouseLeave={(e) => e.currentTarget.style.transform = 'none'}
    >
      {icon}{label}
    </button>
  );
}

function RecordBar({ state, elapsed, sessionNum, setSessionNum, onPrimary, courseName, breadcrumb, accentColor }) {
  const showRec = state === 'recording' || state === 'paused';

  return (
    <div style={{
      borderBottom: '1px solid var(--border-soft)',
      background: 'var(--window-bg)',
    }}>
      {/* Course header */}
      <div style={{
        padding: '10px 18px 6px',
        display: 'flex', alignItems: 'baseline', gap: 10,
        borderBottom: '1px solid var(--border-soft)',
      }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: accentColor || 'var(--accent)' }} />
        <span style={{ fontSize: 16, fontWeight: 700 }}>{courseName}</span>
        <span style={{ fontSize: 11.5, color: 'var(--text-faint)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {breadcrumb.map((seg, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span style={{ opacity: 0.5 }}>›</span>}
              <span style={{ color: i === breadcrumb.length - 1 ? 'var(--text-muted)' : 'var(--text-faint)' }}>{seg}</span>
            </React.Fragment>
          ))}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--text-faint)' }}>
          Session
          <input
            type="number"
            value={sessionNum}
            onChange={(e) => setSessionNum(Number(e.target.value || 1))}
            style={{
              marginLeft: 6, width: 50, padding: '2px 6px',
              fontSize: 11.5, fontFamily: 'inherit',
              background: 'transparent',
              border: '1px solid var(--border-soft)', borderRadius: 4,
              color: 'var(--text)',
            }}
          />
        </span>
      </div>

      {/* Record bar row */}
      <div style={{
        padding: '12px 18px',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <PrimaryButton state={state} onClick={onPrimary} />

        {/* Status pill */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '6px 12px',
          background: showRec ? (state === 'recording' ? 'rgba(217,47,47,0.08)' : 'rgba(196,122,23,0.08)') : 'var(--hover)',
          border: `1px solid ${showRec ? (state === 'recording' ? 'rgba(217,47,47,0.18)' : 'rgba(196,122,23,0.18)') : 'var(--border-soft)'}`,
          borderRadius: 18,
          fontSize: 12, fontWeight: 500,
          color: STATE_LABELS[state]?.dot || 'var(--text-muted)',
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: STATE_LABELS[state]?.dot,
            animation: state === 'recording' ? 'pulse-rec 1.2s ease-in-out infinite' : 'none',
          }} />
          {STATE_LABELS[state]?.label || 'Ready'}
        </div>

        <Waveform active={state === 'recording' || state === 'paused'} paused={state === 'paused'} />

        <span style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 14, fontWeight: 500,
          minWidth: 56, textAlign: 'right',
          color: 'var(--text-muted)',
        }}>
          {formatElapsed(elapsed)}
        </span>
      </div>
    </div>
  );
}

Object.assign(window, { RecordBar, STATE_LABELS, formatElapsed });
