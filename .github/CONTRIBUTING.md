# Contributing

Thanks for your interest in improving browser-history-cli!

## Project structure

The entire tool is a single file — `browser_history.py` — with one runtime dependency (`rich`). Keep it that way unless there's a very strong reason to split.

## Setup

```bash
git clone https://github.com/shguddn8591/browser-history-cli.git
cd browser-history-cli
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Ways to contribute

### Add a browser
Edit `_browser_catalog()` in `browser_history.py`. Add the browser key, display name, `db_type` (`chromium`, `firefox`, or `safari`), and the platform-specific DB path(s).

### Add a domain category
Add entries to `CATEGORY_MAP` near the top of the file. Use an existing category key (`dev`, `work`, `social`, `video`, etc.) or add a new one to both `CATEGORY_MAP` and `CATEGORY_META`.

### Add a command
1. Write a `cmd_<name>(args)` function following the existing pattern.
2. Register a subparser in `main()`.
3. Add the command to the `dispatch` dict in `main()`.
4. Add a usage example to the `epilog` string.

## Code style

- Keep type hints consistent with the rest of the file.
- Use `console.print()` (rich) for all user-facing output — never bare `print()`.
- Handle `PermissionError` and SQLite exceptions gracefully with helpful messages.
- Test manually on your platform before submitting — run `browser-history stats` and `browser-history insights`.

## Pull requests

- One feature or fix per PR.
- Include a clear description of what changed and why.
- If you're adding a browser, mention which OS and version you tested on.
