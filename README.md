# Browser History Analyzer CLI

Analyze your browser history from the terminal — top sites, time spent, productivity score, category breakdown, and beautiful visualizations.

**Platforms**: macOS · Windows · Linux
**Browsers**: Chrome · Firefox · Arc · Brave · Edge · Vivaldi · Opera · Safari

---

## Features

- **Top sites** — ranked by visit count or time spent
- **Category breakdown** — Social / Dev / AI Tools / Video / Work / Shopping / …
- **Productivity score** — 0–100 score based on how you actually spend your time
- **Hourly heatmap** — see when you browse the most
- **GitHub-style activity calendar** — 24-week contribution graph in your terminal
- **`search`** — find any URL or page title in your history
- **`export`** — CSV, JSON, or interactive HTML report (Chart.js, no server needed)
- **`today` / `week`** — instant daily or weekly digest
- Reads all installed browsers simultaneously; no configuration needed
- Data stays **100% local** — nothing is uploaded or transmitted
- Browser can stay open — reads a safe temp copy of the DB

---

## Supported Browsers

| Browser  | macOS | Windows | Linux |
|----------|-------|---------|-------|
| Chrome   | ✅    | ✅      | ✅    |
| Firefox  | ✅    | ✅      | ✅    |
| Brave    | ✅    | ✅      | ✅    |
| Edge     | ✅    | ✅      | ✅    |
| Vivaldi  | ✅    | ✅      | ✅    |
| Opera    | ✅    | ✅      | ✅    |
| Arc      | ✅    | ✅      | ❌    |
| Safari   | ⚠️   | ❌      | ❌    |

> **Safari** requires Full Disk Access for your terminal app.
> System Settings → Privacy & Security → Full Disk Access → add Terminal / iTerm2.

---

## Installation

**Requirements**: Python 3.9+

```bash
# 1. Clone
git clone <repo-url>
cd browser-history-cli

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install
pip install -e .
```

After this, `browser-history` is available as a global command inside the venv.

---

## Usage

```
browser-history <command> [options]
```

### Commands

| Command    | Description                                    |
|------------|------------------------------------------------|
| `stats`    | Full statistics dashboard (default)            |
| `top`      | Top sites ranking                              |
| `search`   | Search history by keyword or regex             |
| `export`   | Export to CSV / JSON / HTML                    |
| `category` | Category & productivity analysis               |
| `today`    | Quick summary of today's browsing              |
| `week`     | Quick summary of this week                     |
| `browsers` | List all detected browsers                     |

### Common options

| Option              | Description                                          | Default    |
|---------------------|------------------------------------------------------|------------|
| `--browser`, `-b`   | Specific browser (`chrome`, `firefox`, `arc`, …)     | all        |
| `--days`, `-d`      | Limit to last N days                                 | all time   |
| `--top`, `-t`       | Number of sites to show                              | 20         |
| `--sort`, `-s`      | Sort by `count` or `duration`                        | `count`    |

---

## Examples

```bash
# Full stats across all browsers
browser-history stats

# Chrome only, last 7 days
browser-history stats --browser chrome --days 7

# Quick daily / weekly digest
browser-history today
browser-history week

# Top 30 sites sorted by time spent
browser-history top --sort duration --limit 30

# Search history (supports --regex)
browser-history search "github"
browser-history search "python tutorial" --days 30
browser-history search "react|vue|svelte" --regex

# Category & productivity analysis
browser-history category
browser-history category --detail --days 7

# Export
browser-history export --format html -o report.html   # interactive charts
browser-history export --format csv  -o history.csv
browser-history export --format json | jq .summary

# List detected browsers
browser-history browsers
```

---

## Output Overview

**Stats dashboard** includes:
- Summary card (visits · unique domains · total time · **productivity score**)
- Top sites table with category labels
- Category breakdown bar chart
- Hourly activity heatmap
- Day-of-week distribution
- **24-week GitHub-style activity calendar**
- 14-day daily trend

**HTML export** generates a self-contained file with interactive Chart.js charts:
- Top 20 sites by visits and time
- Hourly pattern
- Category pie chart

---

## Categories

Domains are automatically classified into:

`AI Tools` · `Development` · `Work` · `Education` · `Social Media` · `Video` · `Entertainment` · `Gaming` · `News` · `Finance` · `Shopping` · `Maps` · `Search` · `Reference` · `Other`

---

## Privacy

- All processing happens locally on your machine.
- The tool copies the browser DB to a secure temporary file (`tempfile.mkstemp`) and deletes it immediately after reading.
- No data is sent to any server.

---

## License

MIT
