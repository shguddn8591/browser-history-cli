# Browser History CLI — Claude Instructions

## Project Overview

A single-file Python CLI tool (`browser_history.py`) that reads and analyzes browser history SQLite databases across multiple browsers and platforms.

**Supported browsers:** Arc, Chrome, Brave, Edge, Vivaldi, Opera, Firefox, Safari
**Platforms:** macOS, Windows, Linux
**Dependencies:** Python ≥ 3.9, `rich` ≥ 13.0 (terminal UI only)
**Entry point:** `python3 browser_history.py <command> [options]`

### Key Commands
```
stats      # Overall visit statistics by browser/category
top        # Top domains ranked by visits or duration
browsers   # List detected browsers and their DB paths
search     # Search history by keyword
export     # Export history to CSV or JSON
```

---

## Architecture & Technical Notes

### Single-file design
All logic lives in `browser_history.py`. Do not split into modules unless the file significantly exceeds maintainability — keep it simple.

### Epoch conversions
Each browser family uses a different epoch. Never mix them up:
- **Chromium** (Arc, Chrome, Brave, Edge, Vivaldi, Opera): microseconds since **1601-01-01**
- **Firefox**: microseconds since **1970-01-01** (standard Unix epoch)
- **Safari**: seconds since **2001-01-01** (Apple CoreData epoch)

### SQLite access
Browser databases are locked while the browser is running. The tool copies the DB to a temp file before reading — always use `shutil.copy2()` + `tempfile` pattern and clean up after.

### Safari permission limitation
Safari's `History.db` requires Full Disk Access on macOS. Handle `PermissionError` gracefully with a helpful message pointing to System Settings → Privacy & Security → Full Disk Access.

### Internal URL filtering
Always exclude `INTERNAL_PREFIXES` (chrome://, about:, moz-extension://, etc.) from all analysis results.

### Rich library usage
Use `rich` for all terminal output (tables, panels, progress spinners). Never use bare `print()` for user-facing output — use `console.print()`.

---

## Workflow

### 1. Plan before acting
- For any non-trivial task (3+ steps or architectural decisions), enter plan mode first.
- Stop immediately if something unexpected arises — re-plan rather than pushing through.
- Write a detailed spec upfront to reduce ambiguity.

### 2. Sub-agent strategy
- Delegate research, exploration, and parallel analysis to sub-agents to keep the main context clean.
- Assign one focused task per sub-agent.

### 3. Self-improvement loop
- After receiving a correction, update `tasks/lessons.md` with the pattern.
- Write rules for yourself so you don't repeat the same mistake.
- Review lessons at the start of sessions on this project.

### 4. Validate before marking done
- Never mark a task complete without proving it works.
- Run the CLI command, check the output, verify edge cases.
- Ask yourself: "Would a staff engineer approve this?"

### 5. Pursue elegance (with balance)
- For non-trivial changes, pause and ask: "Is there a more elegant approach?"
- If a fix feels like a patch, think: "Given everything I know, let me implement this properly."
- Skip this for simple, obvious fixes — avoid over-engineering.
- Critically review your own output before presenting it.

### 6. Autonomous bug fixing
- When given a bug report, just fix it. Don't ask for help step-by-step.
- Point out what the error is, then resolve it.
- Don't require the user to context-switch.

---

## Testing Approach

This project has no automated test suite. Validate changes manually:

1. **Run the affected command** with real browser data and confirm output is correct.
2. **Test edge cases specific to this tool:**
   - Browser is currently open (locked DB)
   - Safari without Full Disk Access (permission error)
   - `--days` filtering (None = all time, int = last N days)
   - A browser that is installed but has no history
   - Running on a platform where a browser doesn't exist
3. **Check all supported platforms** mentally — macOS paths differ from Windows/Linux.
4. **Verify epoch math** whenever touching timestamp conversion logic. Off-by-one errors here cause wildly wrong dates.

---

## Task Management

1. **Plan first** — write a checklist in `tasks/todo.md` before implementing.
2. **Get alignment** — confirm the plan before starting non-trivial work.
3. **Track progress** — check off items as you go.
4. **Summarize changes** — provide a high-level summary at each step.
5. **Document outcomes** — add a review section to `tasks/todo.md` when done.
6. **Record lessons** — update `tasks/lessons.md` after any correction.

---

## Core Principles

- **Simplicity first** — keep changes as small as possible. Minimize code surface area.
- **No laziness** — find the root cause. No band-aids. Hold to senior engineer standards.
- **Minimal blast radius** — touch only what is necessary. Avoid introducing new bugs.
- **Respect the single-file constraint** — don't add files or modules without a strong reason.
- **Privacy awareness** — this tool reads sensitive personal data (browsing history). Never log raw URLs or titles to files. Never transmit data externally. Export only when the user explicitly requests it.
- **Cross-platform correctness** — always consider macOS, Windows, and Linux path differences when touching browser detection or DB path logic.
