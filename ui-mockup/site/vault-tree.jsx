// Vault tree component — mirrors an Obsidian vault (folders + .md leaves).

const VAULT_TREE_DATA = [
  {
    name: 'School', kind: 'folder', children: [
      { name: 'CS446 — Algorithms', kind: 'folder', children: [
        { name: 'Lectures', kind: 'folder', children: [
          { name: 'Lecture-01.md', kind: 'note' },
          { name: 'Lecture-02.md', kind: 'note' },
          { name: 'Lecture-03.md', kind: 'note' },
          { name: 'Lecture-04.md', kind: 'note' },
          { name: 'Lecture-05.md', kind: 'note' },
        ]},
        { name: 'Assignments', kind: 'folder', children: [
          { name: 'PS-01.md', kind: 'note' },
          { name: 'PS-02.md', kind: 'note' },
        ]},
        { name: 'Reading Notes', kind: 'folder', children: [] },
      ]},
      { name: 'ECE220 — Computer Systems', kind: 'folder', children: [
        { name: 'Lectures', kind: 'folder', children: [
          { name: 'Lecture-01.md', kind: 'note' },
          { name: 'Lecture-02.md', kind: 'note' },
        ]},
        { name: 'Labs', kind: 'folder', children: [] },
      ]},
      { name: 'PHYS214', kind: 'folder', children: [] },
    ],
  },
  {
    name: 'Work', kind: 'folder', children: [
      { name: '1on1s', kind: 'folder', children: [
        { name: 'Manager', kind: 'folder', children: [
          { name: '2026-04-12.md', kind: 'note' },
          { name: '2026-04-19.md', kind: 'note' },
        ]},
        { name: 'Skip', kind: 'folder', children: [] },
      ]},
      { name: 'Team Standup', kind: 'folder', children: [
        { name: '2026-04-22.md', kind: 'note' },
      ]},
      { name: 'Interviews', kind: 'folder', children: [] },
    ],
  },
  {
    name: 'Personal', kind: 'folder', children: [
      { name: 'Idea Capture', kind: 'folder', children: [
        { name: 'shower-thoughts.md', kind: 'note' },
      ]},
      { name: 'Books', kind: 'folder', children: [] },
    ],
  },
];

// Topics — bookmarks that point at a vault path.
const TOPICS_DATA = [
  { id: 't1', name: 'CS446',         path: 'School/CS446 — Algorithms/Lectures',     color: '#c2410c' },
  { id: 't2', name: 'ECE220',        path: 'School/ECE220 — Computer Systems/Lectures', color: '#be185d' },
  { id: 't3', name: 'Manager 1:1',   path: 'Work/1on1s/Manager',                      color: '#1c8b4a' },
  { id: 't4', name: 'Idea Capture',  path: 'Personal/Idea Capture',                   color: '#76746b' },
];

const ChevIcon = ({ open }) => (
  <svg width="10" height="10" viewBox="0 0 10 10" style={{ flexShrink: 0, transition: 'transform 120ms ease', transform: open ? 'rotate(90deg)' : 'rotate(0)' }}>
    <path d="M3 1.5 L7 5 L3 8.5" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const FolderIcon = ({ open, color }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" style={{ flexShrink: 0 }}>
    {open ? (
      <>
        <path d="M1.5 4 L4.5 4 L5.5 5 L12 5 L12 11 Q12 12 11 12 L2.5 12 Q1.5 12 1.5 11 Z" fill={color || '#d1cfc4'} stroke={color ? color : '#a8a69a'} strokeWidth="0.8" />
        <path d="M1.5 4 L1.5 3 Q1.5 2 2.5 2 L5 2 L6 3 L11 3 Q12 3 12 4 L12 5" fill="none" stroke={color ? color : '#a8a69a'} strokeWidth="0.8" />
      </>
    ) : (
      <path d="M1.5 3 Q1.5 2 2.5 2 L5 2 L6 3 L11 3 Q12 3 12 4 L12 11 Q12 12 11 12 L2.5 12 Q1.5 12 1.5 11 Z" fill={color || '#d1cfc4'} stroke={color ? color : '#a8a69a'} strokeWidth="0.8" />
    )}
  </svg>
);

const NoteIcon = () => (
  <svg width="11" height="11" viewBox="0 0 12 12" style={{ flexShrink: 0, opacity: 0.7 }}>
    <path d="M3 1.5 L8 1.5 L10 3.5 L10 10 Q10 10.5 9.5 10.5 L3 10.5 Q2.5 10.5 2.5 10 L2.5 2 Q2.5 1.5 3 1.5 Z M8 1.5 L8 3.5 L10 3.5" fill="none" stroke="currentColor" strokeWidth="0.8" strokeLinejoin="round" />
    <line x1="4" y1="6" x2="8" y2="6" stroke="currentColor" strokeWidth="0.8" />
    <line x1="4" y1="7.6" x2="8" y2="7.6" stroke="currentColor" strokeWidth="0.8" />
    <line x1="4" y1="9.2" x2="6.5" y2="9.2" stroke="currentColor" strokeWidth="0.8" />
  </svg>
);

const RecHerePill = ({ onClick }) => (
  <button
    onClick={(e) => { e.stopPropagation(); onClick && onClick(); }}
    style={{
      marginLeft: 'auto', flexShrink: 0,
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 10, fontWeight: 600, letterSpacing: 0.2,
      padding: '2px 7px',
      background: 'var(--accent)', color: '#fff',
      border: 'none', borderRadius: 10,
      opacity: 0,
    }}
    className="rec-here-pill"
  >
    <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff', display: 'inline-block' }} />
    Rec here
  </button>
);

function TreeNode({ node, path, depth, expanded, setExpanded, target, onTargetChange, onRecordHere, accent }) {
  const isFolder = node.kind === 'folder';
  const childPath = path ? `${path}/${node.name}` : node.name;
  const isOpen = expanded.has(childPath);
  const isTarget = target === childPath;
  const isOnTargetPath = target && (target === childPath || target.startsWith(childPath + '/'));

  const toggle = () => {
    setExpanded(prev => {
      const n = new Set(prev);
      if (n.has(childPath)) n.delete(childPath); else n.add(childPath);
      return n;
    });
  };

  const onRowClick = () => {
    if (isFolder) {
      if (!isOpen) toggle();
      onTargetChange(childPath);
    }
  };

  const rowStyle = {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '4px 10px 4px 0',
    paddingLeft: 10 + depth * 14,
    fontSize: 12.5,
    color: isFolder ? 'var(--text)' : 'var(--text-muted)',
    cursor: 'pointer',
    position: 'relative',
    borderRadius: 5,
    margin: '0 6px',
    background: isTarget ? 'var(--selected-strong)' : 'transparent',
    fontWeight: isTarget ? 600 : (isOnTargetPath && isFolder ? 500 : 400),
    transition: 'background 80ms ease',
  };

  return (
    <div>
      <div
        onClick={onRowClick}
        className="vault-row"
        style={rowStyle}
        onMouseEnter={(e) => { if (!isTarget) e.currentTarget.style.background = 'var(--hover)'; const pill = e.currentTarget.querySelector('.rec-here-pill'); if (pill) pill.style.opacity = '1'; }}
        onMouseLeave={(e) => { if (!isTarget) e.currentTarget.style.background = 'transparent'; const pill = e.currentTarget.querySelector('.rec-here-pill'); if (pill) pill.style.opacity = '0'; }}
      >
        {isTarget && (
          <span style={{ position: 'absolute', left: 0, top: 4, bottom: 4, width: 2.5, borderRadius: 2, background: accent }} />
        )}
        {isFolder ? (
          <span onClick={(e) => { e.stopPropagation(); toggle(); }} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 12, height: 12, color: 'var(--text-muted)' }}>
            <ChevIcon open={isOpen} />
          </span>
        ) : (
          <span style={{ width: 12, height: 12 }} />
        )}
        {isFolder
          ? <FolderIcon open={isOpen} color={isOnTargetPath ? '#ddb18d' : null} />
          : <NoteIcon />}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {isFolder ? node.name : node.name.replace(/\.md$/, '')}
        </span>
        {isFolder && <RecHerePill onClick={() => onRecordHere(childPath)} />}
      </div>
      {isFolder && isOpen && node.children && (
        <div>
          {node.children.map((c, i) => (
            <TreeNode
              key={c.name + i}
              node={c}
              path={childPath}
              depth={depth + 1}
              expanded={expanded}
              setExpanded={setExpanded}
              target={target}
              onTargetChange={onTargetChange}
              onRecordHere={onRecordHere}
              accent={accent}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function VaultTree({ data, target, onTargetChange, onRecordHere, accent }) {
  // expand folders along the target path on first render
  const initial = React.useMemo(() => {
    const set = new Set();
    if (target) {
      const parts = target.split('/');
      for (let i = 1; i <= parts.length; i++) set.add(parts.slice(0, i).join('/'));
    } else {
      set.add('School');
    }
    return set;
  }, []);
  const [expanded, setExpanded] = React.useState(initial);
  return (
    <div className="scroll" style={{ overflowY: 'auto', flex: 1, padding: '4px 0' }}>
      {data.map((n, i) => (
        <TreeNode
          key={n.name + i}
          node={n}
          path=""
          depth={0}
          expanded={expanded}
          setExpanded={setExpanded}
          target={target}
          onTargetChange={onTargetChange}
          onRecordHere={onRecordHere}
          accent={accent}
        />
      ))}
    </div>
  );
}

function TopicRow({ topic, isActive, onClick, photoShape }) {
  const pathSegments = topic.path.split('/');
  const tail = pathSegments.slice(-2).join(' / ');
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 9,
        padding: '6px 12px',
        fontSize: 12.5,
        cursor: 'pointer',
        margin: '0 6px',
        borderRadius: 5,
        background: isActive ? 'var(--selected-strong)' : 'transparent',
        fontWeight: isActive ? 600 : 400,
      }}
      onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = 'var(--hover)'; }}
      onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
    >
      <span style={{
        width: 9, height: 9,
        borderRadius: photoShape === 'square' ? 2 : '50%',
        background: topic.color,
        flexShrink: 0,
      }} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {topic.name}
      </span>
      <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--text-faint)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>
        {tail}
      </span>
    </div>
  );
}

function Sidebar({ target, setTarget, activeTopic, setActiveTopic, onRecordHere, accent, photoShape, density, sidebarMode }) {
  const [vaultCollapsed, setVaultCollapsed] = React.useState(false);
  const [topicsCollapsed, setTopicsCollapsed] = React.useState(false);
  const [vaultHeight, setVaultHeight] = React.useState(0.62);

  const onTopicClick = (t) => {
    setActiveTopic(t.id);
    setTarget(t.path);
  };

  const HEAD = (label, collapsed, setCollapsed, right) => (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: density === 'compact' ? '6px 12px 4px' : '10px 12px 4px',
      fontSize: 10, fontWeight: 700, letterSpacing: 0.8,
      color: 'var(--text-faint)', textTransform: 'uppercase',
      cursor: 'pointer', userSelect: 'none',
    }} onClick={() => setCollapsed(!collapsed)}>
      <span style={{ display: 'inline-flex', transform: collapsed ? 'rotate(0)' : 'rotate(90deg)', transition: 'transform 120ms ease' }}>
        <ChevIcon open={false} />
      </span>
      {label}
      <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 4, color: 'var(--text-muted)' }}>{right}</span>
    </div>
  );

  // Hide vault entirely if sidebarMode is 'topics-only' (one of the tweak variants)
  const showVault = sidebarMode !== 'topics-only';
  const showTopics = sidebarMode !== 'vault-only';

  return (
    <div style={{
      width: 248, flexShrink: 0,
      background: 'var(--sidebar-bg)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Sidebar topbar — vault name */}
      <div style={{
        height: 38,
        padding: '0 12px',
        display: 'flex', alignItems: 'center', gap: 8,
        borderBottom: '1px solid var(--border-soft)',
        fontSize: 12.5, fontWeight: 600,
      }}>
        <svg width="13" height="13" viewBox="0 0 14 14"><path d="M2 3 L2 11 Q2 12 3 12 L11 12 Q12 12 12 11 L12 4 Q12 3 11 3 L7 3 L6 2 L3 2 Q2 2 2 3 Z" fill="#7e6e57" /></svg>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>my-vault</span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-faint)', fontSize: 10, fontWeight: 500 }}>~/Obsidian</span>
      </div>

      {showVault && (
        <div style={{
          flex: vaultHeight,
          minHeight: 100,
          display: 'flex', flexDirection: 'column',
          borderBottom: showTopics ? '1px solid var(--border-soft)' : 'none',
        }}>
          {HEAD('Vault', vaultCollapsed, setVaultCollapsed,
            <>
              <button title="New folder" style={iconBtn}>+</button>
              <button title="Refresh" style={iconBtn}>⟳</button>
            </>
          )}
          {!vaultCollapsed && (
            <VaultTree
              data={VAULT_TREE_DATA}
              target={target}
              onTargetChange={setTarget}
              onRecordHere={onRecordHere}
              accent={accent}
            />
          )}
        </div>
      )}

      {showTopics && (
        <div style={{
          flex: showVault ? 1 - vaultHeight : 1,
          minHeight: 80,
          display: 'flex', flexDirection: 'column',
        }}>
          {HEAD('Topics', topicsCollapsed, setTopicsCollapsed,
            <button title="Add topic" style={iconBtn}>+</button>
          )}
          {!topicsCollapsed && (
            <div className="scroll" style={{ overflowY: 'auto', flex: 1, padding: '2px 0' }}>
              {TOPICS_DATA.map(t => (
                <TopicRow key={t.id} topic={t} isActive={activeTopic === t.id} onClick={() => onTopicClick(t)} photoShape={photoShape} />
              ))}
            </div>
          )}
        </div>
      )}

      <div style={{
        borderTop: '1px solid var(--border-soft)',
        padding: '6px 8px',
        display: 'flex', gap: 4,
      }}>
        <button style={{ ...sidebarFootBtn, flex: 1 }}>⚙ Settings</button>
      </div>
    </div>
  );
}

const iconBtn = {
  background: 'transparent',
  border: 'none',
  color: 'var(--text-muted)',
  fontSize: 12,
  width: 18, height: 18,
  borderRadius: 4,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  padding: 0, lineHeight: 1,
};

const sidebarFootBtn = {
  background: 'transparent',
  border: 'none',
  fontSize: 12,
  color: 'var(--text-muted)',
  textAlign: 'left',
  padding: '6px 8px',
  borderRadius: 4,
};

Object.assign(window, { Sidebar, VAULT_TREE_DATA, TOPICS_DATA });
