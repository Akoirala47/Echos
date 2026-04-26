# Echos — SPEC Addendum (April 2026)

> Two cohesion fixes to the existing SPEC.md. These are additive/overrides,
> not a rewrite. Cross-reference the section numbers in `SPEC.md`.

---

## A. Recording Controls — separate "Pause" from "End Session"

### Problem
- The big record button doubles as both **Start** and **Stop**, so once you
  hit Start the same button becomes "Stop Recording" — a single mistaken
  click during a lecture/meeting permanently ends the session.
- Once a session is stopped, the file is closed: there is no way to resume
  capture into the same lecture file. This is jarring when the user only
  meant to take a brief break.
- The Pause button sits next to a destructive Stop, increasing slip risk.

### New behaviour (overrides SPEC §5.2 / US-10 / US-13)

The recording state machine becomes:

```
IDLE ──Start──▶ RECORDING ◀──Resume── PAUSED
                    │   ─────Pause────▶
                    │
                    └────End Session──▶ STOPPED  (terminal for that session)
```

- The **primary in-session control is Pause/Resume only.** Once recording
  starts, the prominent button in the record bar becomes a Pause button
  (and toggles to Resume when paused). It never says "Stop".
- **End Session** is a separate, lower-emphasis control placed away from
  the primary button. It lives:
  - in the **status bar** (right side) labelled *End Session*, and
  - in the **File menu** as `End Session` (`⌘⇧E`).
  - It is **never** placed adjacent to Start/Pause.
- Clicking End Session shows a confirm dialog: *"End this session? You
  won't be able to add more audio to this lecture."* (Yes / Cancel).
  Confirmation is required because the action is destructive of session
  continuity.
- Pause does **not** finalise the file. The transcript-so-far stays
  editable; the session remains in `PAUSED`. The user may resume any
  number of times.
- Audio captured between Pause and Resume is dropped (mic stream is
  suspended) — same as today; the difference is the user always has a
  way back into RECORDING without losing the session.
- After End Session, the bar shows a calm "Session complete" state with
  two actions: **Generate Notes** (primary) and **Start New Session**
  (secondary). Start New Session is the only way back to IDLE.

### UI deltas

| Element | Before | After |
|---|---|---|
| Primary button (idle) | `● Start Recording` | `● Start Recording` (unchanged) |
| Primary button (recording) | `■ Stop Recording` (red) | `❚❚ Pause` (amber) |
| Primary button (paused) | `■ Stop Recording` (amber) | `▶ Resume` (green) |
| Secondary inline button | `⏸ Pause` | *(removed)* |
| End Session control | n/a (folded into Stop) | Status bar, right side, ghost button. Confirms before firing. |
| Keyboard | `⌘R` toggles record/stop, `⌘P` pause | `⌘R` Start / Resume, `⌘P` Pause, `⌘⇧E` End Session |

### State labels (status bar dot)

| State | Color | Label |
|---|---|---|
| IDLE | grey | Ready |
| RECORDING | red (pulsing) | Recording · MM:SS |
| PAUSED | amber | Paused · MM:SS |
| STOPPED | grey | Session complete · MM:SS |
| GENERATING | blue | Generating notes… |
| NOTES_DONE | green | Notes ready |
| SAVED | green | Saved · {filename} |

---

## B. Sidebar — Mirror the Obsidian Vault Tree

### Problem
Sidebar today is a flat "Topics/Courses" list. Users have no idea where
their notes actually land in the vault, and it doesn't reflect Obsidian's
folder hierarchy. Power users with nested vault structures
(e.g. `School/CS446/Lectures`, `Work/1on1s/Manager`) can't see, navigate,
or pick a target inside the app.

### New behaviour (overrides SPEC §5.1 sidebar / US-04..US-09)

The sidebar becomes a **two-section panel**:

```
┌──────────────────────────┐
│ VAULT                    │
│  📁 School               │
│   └ 📁 CS446             │
│      └ 📁 Lectures       │  ← current target (highlighted)
│         · Lecture-01.md  │
│         · Lecture-02.md  │
│      └ 📁 Assignments    │
│   └ 📁 ECE220            │
│  📁 Work                 │
│   └ 📁 1on1s             │
│  📁 Personal             │
│                          │
│ + New Folder    ⟳ Refresh│
├──────────────────────────┤
│ TOPICS                   │
│  ● CS446 → School/CS446… │
│  ● Manager 1:1 → Work/…  │
│  ● Idea Capture → Persona│
│ + Add Topic              │
└──────────────────────────┘
│ ⚙ Settings               │
└──────────────────────────┘
```

- Top section: **VAULT TREE** — live mirror of the user's Obsidian
  vault on disk. Folders are expandable (chevron + indent). Existing
  `.md` notes show as leaves with their filename (sans extension).
  The currently-targeted folder is highlighted with the active topic's
  accent color.
- Bottom section: **TOPICS** — the existing topic concept, but each
  topic is now just a *named bookmark* that points at a folder path
  inside the vault. Selecting a topic expands the tree to that folder
  and sets it as the recording target. Topics still have a color dot
  and reorder/delete behaviour from US-06/US-07.
- The two sections are **resizable** (drag handle between them);
  collapsible via header chevron.
- **Hover on any folder** reveals a "Record here" affordance — lets
  users drop a one-off note into any folder without first creating a
  topic.
- **Right-click on folder**: New Subfolder / Rename / Reveal in Finder.
- **Right-click on .md leaf**: Open in Obsidian / Reveal in Finder.

### Data model additions (extends SPEC §3)

```jsonc
// Course (renamed Topic in UI, key stays for backwards compat)
{
  "id": "uuid",
  "name": "string",
  "folder": "School/CS446/Lectures",   // now a full vault-relative path
  "color": "#hex"
}
```

Migration: existing courses with single-segment `folder` keep working —
the tree just shows them at the vault root.

### Filesystem watching

A `VaultWatcher` (QFileSystemWatcher) keeps the tree in sync with disk
changes (new files from Obsidian, renamed folders, etc.) without polling.
Refresh button forces a manual rescan.

### UI deltas

| Element | Before | After |
|---|---|---|
| Sidebar header | `TOPICS` | Two: `VAULT` and `TOPICS` |
| Folder hierarchy | none | full nested tree with chevrons |
| Existing notes visible | no | yes, as `.md` leaves |
| Target indicator | implicit | folder highlight + breadcrumb in course header |
| Course header | `CS446 — Lecture 5` | `CS446 — Lecture 5  ›  School / CS446 / Lectures` |

---

## C. Out of scope for this addendum
- Drag-to-move notes between folders (keep this as a future task)
- Vault search inside the sidebar (separate feature)
- Multi-vault support
