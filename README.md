# browser-history-cli

[![PyPI version](https://img.shields.io/pypi/v/browser-history-cli)](https://pypi.org/project/browser-history-cli/)
[![Python](https://img.shields.io/pypi/pyversions/browser-history-cli)](https://pypi.org/project/browser-history-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)]()

**Turn your browser history into actionable insights — right in your terminal.**

```
pip install browser-history-cli
browser-history insights
```

No accounts. No cloud. Your data never leaves your machine.

---

## What it does

`browser-history-cli` reads the SQLite databases your browsers already store locally and gives you a clear picture of how you actually spend your time online — across every browser, on any OS.

```
╭─────────────────── Insights — All browsers · last 30d ───────────────────╮
│                                                                           │
│  → Most visited: github.com  (1,842 visits · Development)                │
│  → Peak browsing hour: 10am  (312 visits)                                 │
│  → Most active period: morning (6–12)  (2,341 visits)                    │
│  → You browse 1.8× more on weekends than weekdays                        │
│  → Biggest leisure sink: Video  (4h 23m spent)                           │
│  → Busiest day: 2024-03-11 (Mon)  — 487 visits                           │
│  → Daily average: 156 visits across 28 active days                       │
│  → Active streak: 12 consecutive days                                     │
│  → Morning routine (6–10am): github.com → chatgpt.com → notion.so        │
│  → Explored 634 unique domains                                            │
│  → Productivity: 71/100  — impressive focus                               │
│                                                                           │
╰───────────────────────────────────────────────────────────────────────────╯
```

---

## Features

| Command | Description |
|---------|-------------|
| `stats` | Full dashboard: top sites, categories, heatmaps, trend charts |
| `insights` | Smart behavioral observations from your browsing patterns |
| `compare` | Side-by-side comparison of this week vs last week (or month) |
| `timeline` | Hour-by-hour activity view for any day |
| `today` | Quick summary of today's browsing |
| `week` | This week's summary |
| `top` | Top domains ranked by visits or time spent |
| `category` | Category & productivity breakdown |
| `search` | Full-text search across URLs and page titles |
| `export` | Export to CSV, JSON, or a standalone HTML report |
| `browsers` | List all detected browsers on your system |

---

## Installation

```bash
# Recommended — isolated install
pipx install browser-history-cli

# Or with pip
pip install browser-history-cli
```

**Requirements:** Python 3.9+ · [`rich`](https://github.com/Textualize/rich)

---

## Quick start

```bash
# See everything about your browsing habits
browser-history stats

# Smart insights in one panel
browser-history insights

# How did this week compare to last week?
browser-history compare

# What did I do all day?
browser-history timeline

# Specific date
browser-history timeline --date 2024-03-10

# Last 7 days, one browser only
browser-history stats --browser arc --days 7

# Top 20 sites by time spent
browser-history top --sort duration

# Where does my social media time go?
browser-history category --detail

# Search your history
browser-history search "react hooks" --days 30

# Export a shareable HTML report
browser-history export --format html -o report.html
```

---

## Supported browsers

| Browser | macOS | Windows | Linux |
|---------|:-----:|:-------:|:-----:|
| Arc | ✅ | ✅ | — |
| Chrome | ✅ | ✅ | ✅ |
| Brave | ✅ | ✅ | ✅ |
| Edge | ✅ | ✅ | ✅ |
| Vivaldi | ✅ | ✅ | ✅ |
| Opera | ✅ | ✅ | ✅ |
| Firefox | ✅ | ✅ | ✅ |
| Safari | ✅* | — | — |

\*Safari requires Full Disk Access for your terminal app.
**System Settings → Privacy & Security → Full Disk Access**

---

## Example outputs

### `stats` — Full dashboard

```
╭──────────── Arc  (last 7d) ────────────╮
│  Visits:           4,231               │
│  Unique domains:   312                 │
│  Total time:       6.2h                │
│  Productivity:     68/100              │
│  Period:           2024-03-08 → 03-14  │
╰────────────────────────────────────────╯

╭─────────────── Top 20 Sites ───────────────╮
│  #   Domain               Cat      Visits  │
│  1   github.com           Dev       1,842  │
│  2   chatgpt.com          AI          934  │
│  3   stackoverflow.com    Dev         721  │
│  4   youtube.com          Video       543  │
│  5   notion.so            Work        412  │
│  …                                         │
╰────────────────────────────────────────────╯

Hourly pattern
0h                     12h                    23h
░░░░░░▒▒▓▓█████████▓▓▓▒▒▒░░░░
  Peak: 10:00(312), 11:00(298), 14:00(267)

Activity calendar (last 24 weeks)
     Jan         Feb         Mar
Mo  ░░░░▒▒▒▒▓▓▓▓▓▓▓▓█████████
Tu  ░░▒▒▒▒▒▒▓▓▓▓▓▓▓▓▓▓███████
We  ░░░░▒▒▒▒▒▒▓▓▓▓▓▓▓▓▓▓█████
…
```

### `compare` — Period comparison

```
╭───────── Last week vs This week ─────────╮
│  Metric          Last week   This week   │
│  Total visits    3,841       4,231  +10% │
│  Unique domains  287         312     +9% │
│  Total time      5.1h        6.2h   +22% │
│  Productivity    54/100      68/100 +26% │
│  Top site        youtube.com github.com  │
╰──────────────────────────────────────────╯

New this week:  perplexity.ai  rust-lang.org  docs.rs
No longer visited:  twitch.tv  reddit.com

Biggest increases:
  github.com                       312 →  891  +186%
  stackoverflow.com                145 →  312  +115%

Biggest decreases:
  youtube.com                      543 →  201   -63%
```

### `timeline` — Day view

```
Activity Timeline — 2024-03-14 (Thu)  312 visits

  09:00   47  ████████████████████  github.com×18  chatgpt.com×12  notion.so
  10:00   52  ████████████████████  github.com×21  stackoverflow.com×15
  11:00   38  ████████████████      chatgpt.com×14  docs.python.org×9
  12:00   12  █████                 naver.com×6  youtube.com×4
  13:00    8  ███                   youtube.com×5
  14:00   41  █████████████████     github.com×19  vercel.com×11
  21:00   22  █████████             reddit.com×8  youtube.com×7
```

---

## How it works

- Reads SQLite databases that browsers already maintain locally
- Copies each DB to a temp file before reading (no writes, no locks)
- Filters out internal browser URLs (`chrome://`, `about:`, etc.)
- Categorizes domains using a built-in map of 110+ domains + keyword fallback
- Calculates productivity scores based on category time distribution
- **Never uploads any data** — everything runs locally

---

## Privacy

This tool reads sensitive personal data. It is designed with privacy in mind:

- All processing happens locally on your machine
- No data is sent to any server
- Exported files are created only when explicitly requested
- The source code is a single readable Python file — inspect it yourself

---

## Contributing

The entire tool is a single file (`browser_history.py`) with one runtime dependency (`rich`).

**Adding a browser:** Edit `_browser_catalog()` with the platform-specific DB path and `db_type`.

**Adding a domain category:** Add entries to `CATEGORY_MAP` at the top of the file.

**Adding a command:** Follow the existing pattern — a `cmd_*` function and a subparser registration in `main()`.

---

## License

MIT
