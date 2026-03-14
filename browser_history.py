#!/usr/bin/env python3
"""
Browser History Analyzer CLI
Supports: Arc, Chrome, Brave, Edge, Vivaldi, Opera, Firefox, Safari
Platforms: macOS, Windows, Linux
"""

import argparse
import contextlib
import csv
import glob
import json
import os
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
from urllib.parse import urlparse

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    print("rich is required: pip install rich")
    sys.exit(1)

console = Console()
SYSTEM = platform.system()  # 'Darwin' | 'Windows' | 'Linux'

# ---------------------------------------------------------------------------
# Internal URL prefixes — excluded from all analysis
# ---------------------------------------------------------------------------
INTERNAL_PREFIXES = (
    "chrome://", "arc://", "about:", "moz-extension://",
    "chrome-extension://", "edge://", "brave://", "vivaldi://",
    "opera://", "file://", "data:", "javascript:",
)

# ---------------------------------------------------------------------------
# Epoch constants
# ---------------------------------------------------------------------------
CHROMIUM_EPOCH = datetime(1601, 1, 1)
UNIX_EPOCH = datetime(1970, 1, 1)
SAFARI_EPOCH = datetime(2001, 1, 1)

# ---------------------------------------------------------------------------
# Domain → Category mapping
# Productivity tiers:  productive | neutral | leisure
# ---------------------------------------------------------------------------
CATEGORY_MAP: dict[str, str] = {
    # --- AI Tools ---
    "chat.openai.com": "ai", "chatgpt.com": "ai",
    "claude.ai": "ai", "gemini.google.com": "ai",
    "perplexity.ai": "ai", "copilot.microsoft.com": "ai",
    "bard.google.com": "ai", "poe.com": "ai",
    "huggingface.co": "ai", "replicate.com": "ai",

    # --- Development ---
    "github.com": "dev", "gitlab.com": "dev", "bitbucket.org": "dev",
    "stackoverflow.com": "dev", "stackexchange.com": "dev",
    "developer.mozilla.org": "dev", "docs.python.org": "dev",
    "npmjs.com": "dev", "pypi.org": "dev", "crates.io": "dev",
    "codepen.io": "dev", "jsfiddle.net": "dev", "replit.com": "dev",
    "codesandbox.io": "dev", "vercel.com": "dev", "netlify.com": "dev",
    "heroku.com": "dev", "railway.app": "dev", "render.com": "dev",
    "digitalocean.com": "dev", "aws.amazon.com": "dev",
    "cloud.google.com": "dev", "azure.microsoft.com": "dev",
    "leetcode.com": "dev", "hackerrank.com": "dev",
    "school.programmers.co.kr": "dev", "programmers.co.kr": "dev",
    "inflearn.com": "education", "fastcampus.co.kr": "education",

    # --- Work Tools ---
    "notion.so": "work", "notions.so": "work",
    "docs.google.com": "work", "sheets.google.com": "work",
    "slides.google.com": "work", "drive.google.com": "work",
    "office.com": "work", "teams.microsoft.com": "work",
    "slack.com": "work", "discord.com": "work",
    "trello.com": "work", "asana.com": "work",
    "jira.atlassian.com": "work", "confluence.atlassian.com": "work",
    "figma.com": "work", "miro.com": "work",
    "airtable.com": "work", "monday.com": "work",
    "zoom.us": "work", "meet.google.com": "work",
    "mail.google.com": "work", "mail.naver.com": "work",
    "outlook.live.com": "work",

    # --- Social Media ---
    "twitter.com": "social", "x.com": "social",
    "instagram.com": "social", "facebook.com": "social",
    "linkedin.com": "social", "reddit.com": "social",
    "threads.net": "social", "threads.com": "social",
    "tiktok.com": "social", "snapchat.com": "social",
    "pinterest.com": "social", "tumblr.com": "social",
    "mastodon.social": "social", "bsky.app": "social",

    # --- Video / Entertainment ---
    "youtube.com": "video", "youtu.be": "video",
    "netflix.com": "entertainment", "disneyplus.com": "entertainment",
    "twitch.tv": "entertainment", "vimeo.com": "video",
    "wavve.com": "entertainment", "watcha.com": "entertainment",
    "tving.com": "entertainment", "laftel.net": "entertainment",
    "dailymotion.com": "video",

    # --- Gaming ---
    "store.steampowered.com": "gaming", "steamcommunity.com": "gaming",
    "epicgames.com": "gaming", "gog.com": "gaming",
    "nexon.com": "gaming", "maplestory.nexon.com": "gaming",
    "blizzard.com": "gaming", "battle.net": "gaming",
    "lol.op.gg": "gaming", "op.gg": "gaming",

    # --- News ---
    "naver.com": "news", "news.naver.com": "news",
    "daum.net": "news", "news.daum.net": "news",
    "hani.co.kr": "news", "chosun.com": "news",
    "joongang.co.kr": "news", "donga.com": "news",
    "yonhapnews.co.kr": "news",
    "bbc.com": "news", "cnn.com": "news",
    "nytimes.com": "news", "theguardian.com": "news",
    "techcrunch.com": "news", "theverge.com": "news",
    "wired.com": "news", "ycombinator.com": "news",
    "news.ycombinator.com": "news",

    # --- Shopping ---
    "amazon.com": "shopping", "amazon.co.jp": "shopping",
    "coupang.com": "shopping", "gmarket.co.kr": "shopping",
    "11st.co.kr": "shopping", "auction.co.kr": "shopping",
    "musinsa.com": "shopping", "29cm.co.kr": "shopping",
    "oliveyoung.co.kr": "shopping", "kurly.com": "shopping",
    "baemin.com": "shopping", "yogiyo.co.kr": "shopping",

    # --- Finance ---
    "tossinvest.com": "finance", "toss.im": "finance",
    "kiwoom.com": "finance", "miraeasset.com": "finance",
    "samsungpop.com": "finance", "securities.com": "finance",
    "coinbase.com": "finance", "binance.com": "finance",
    "upbit.com": "finance", "bithumb.com": "finance",

    # --- Education ---
    "coursera.org": "education", "udemy.com": "education",
    "khanacademy.org": "education", "edx.org": "education",
    "medium.com": "education", "dev.to": "education",
    "hashnode.com": "education", "substack.com": "education",
    "wikipedia.org": "reference", "namu.wiki": "reference",

    # --- Maps / Navigation ---
    "map.naver.com": "maps", "maps.google.com": "maps",
    "google.com/maps": "maps", "kakaomap.com": "maps",
    "map.kakao.com": "maps",

    # --- Search Engines ---
    "google.com": "search", "search.naver.com": "search",
    "search.daum.net": "search", "bing.com": "search",
    "duckduckgo.com": "search",
}

# Category display metadata: (label, color, productive_tier)
# tiers: 2=productive, 1=neutral, 0=leisure
CATEGORY_META: dict[str, tuple[str, str, int]] = {
    "ai":            ("AI Tools",      "bold magenta",  2),
    "dev":           ("Development",   "bold green",    2),
    "work":          ("Work",          "green",         2),
    "education":     ("Education",     "cyan",          2),
    "reference":     ("Reference",     "cyan",          1),
    "news":          ("News",          "yellow",        1),
    "search":        ("Search",        "dim",           1),
    "maps":          ("Maps",          "dim",           1),
    "finance":       ("Finance",       "yellow",        1),
    "social":        ("Social Media",  "blue",          0),
    "video":         ("Video",         "blue",          0),
    "entertainment": ("Entertainment", "magenta",       0),
    "gaming":        ("Gaming",        "magenta",       0),
    "shopping":      ("Shopping",      "red",           0),
    "other":         ("Other",         "dim",           1),
}


def categorize(domain: str) -> str:
    """Return category key for a domain. Keyword fallback if not in map."""
    domain = domain.lower()
    if domain in CATEGORY_MAP:
        return CATEGORY_MAP[domain]
    # Keyword-based fallback
    for keyword, cat in [
        ("github", "dev"), ("gitlab", "dev"), ("stackoverflow", "dev"),
        ("docs.", "reference"), ("developer.", "dev"),
        ("openai", "ai"), ("anthropic", "ai"), ("claude", "ai"),
        ("youtube", "video"), ("netflix", "entertainment"),
        ("instagram", "social"), ("twitter", "social"), ("reddit", "social"),
        ("amazon", "shopping"), ("naver", "news"), ("kakao", "work"),
        ("local", "dev"), ("localhost", "dev"),
    ]:
        if keyword in domain:
            return cat
    return "other"


def productivity_score(category_duration: dict[str, int]) -> int:
    """Return 0-100 productivity score based on category time distribution."""
    total = sum(category_duration.values())
    if total == 0:
        return 0
    productive = sum(
        v for k, v in category_duration.items()
        if CATEGORY_META.get(k, ("", "", 1))[2] == 2
    )
    leisure = sum(
        v for k, v in category_duration.items()
        if CATEGORY_META.get(k, ("", "", 1))[2] == 0
    )
    score = int((productive / total) * 100 - (leisure / total) * 20)
    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def positive_int(value: str) -> int:
    v = int(value)
    if v <= 0:
        raise argparse.ArgumentTypeError(f"Must be a positive integer, got {v}")
    return v


# ---------------------------------------------------------------------------
# Security-safe temporary DB copy
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def safe_tmp_copy(db_path: str):
    """
    Atomically create a temp file and copy the browser DB into it.
    Uses mkstemp (not deprecated mktemp) to prevent TOCTOU race conditions.
    Guarantees cleanup even on SIGINT.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        shutil.copy2(db_path, tmp_path)
        yield tmp_path
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Time conversions
# ---------------------------------------------------------------------------

def chromium_ts(us: int | None) -> datetime | None:
    if not us:
        return None
    try:
        return CHROMIUM_EPOCH + timedelta(microseconds=us)
    except (OverflowError, OSError):
        return None


def unix_ts(us: int | None) -> datetime | None:
    if not us:
        return None
    try:
        return UNIX_EPOCH + timedelta(microseconds=us)
    except (OverflowError, OSError):
        return None


def safari_ts(s: float | None) -> datetime | None:
    if not s:
        return None
    try:
        return SAFARI_EPOCH + timedelta(seconds=s)
    except (OverflowError, OSError):
        return None


def duration_str(microseconds: int) -> str:
    if not microseconds or microseconds <= 0:
        return "-"
    s = microseconds / 1_000_000
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s/60:.1f}m"
    return f"{s/3600:.1f}h"


# ---------------------------------------------------------------------------
# Browser path detection
# ---------------------------------------------------------------------------

def _firefox_dbs() -> list[str]:
    home = os.path.expanduser("~")
    bases = {
        "Darwin":  os.path.join(home, "Library", "Application Support", "Firefox", "Profiles"),
        "Windows": os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles"),
        "Linux":   os.path.join(home, ".mozilla", "firefox"),
    }
    base = bases.get(SYSTEM, "")
    if not os.path.isdir(base):
        return []
    result = []
    for entry in os.listdir(base):
        profile = os.path.join(base, entry)
        db = os.path.join(profile, "places.sqlite")
        # Resolve symlinks to prevent following malicious links outside the profile dir
        real_db = os.path.realpath(db)
        if os.path.isfile(real_db) and real_db.startswith(os.path.realpath(base)):
            if "default-release" in entry or "default" in entry:
                result.insert(0, real_db)
            else:
                result.append(real_db)
    return result


def _arc_windows() -> list[str]:
    local = os.environ.get("LOCALAPPDATA", "")
    return glob.glob(os.path.join(
        local, "Packages", "TheBrowserCompany.Arc_*",
        "LocalCache", "Local", "Arc", "User Data", "Default", "History"
    ))


def _browser_catalog() -> dict:
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")

    if SYSTEM == "Darwin":
        sup = os.path.join(home, "Library", "Application Support")
        return {
            "arc":     ("Arc",     "chromium", [os.path.join(sup, "Arc", "User Data", "Default", "History")]),
            "chrome":  ("Chrome",  "chromium", [os.path.join(sup, "Google", "Chrome", "Default", "History")]),
            "brave":   ("Brave",   "chromium", [os.path.join(sup, "BraveSoftware", "Brave-Browser", "Default", "History")]),
            "edge":    ("Edge",    "chromium", [os.path.join(sup, "Microsoft Edge", "Default", "History")]),
            "vivaldi": ("Vivaldi", "chromium", [os.path.join(sup, "Vivaldi", "Default", "History")]),
            "opera":   ("Opera",   "chromium", [os.path.join(sup, "com.operasoftware.Opera", "Default", "History")]),
            "safari":  ("Safari",  "safari",   [os.path.join(home, "Library", "Safari", "History.db")]),
            "firefox": ("Firefox", "firefox",  _firefox_dbs()),
        }
    elif SYSTEM == "Windows":
        return {
            "arc":     ("Arc",     "chromium", _arc_windows()),
            "chrome":  ("Chrome",  "chromium", [os.path.join(local, "Google", "Chrome", "User Data", "Default", "History")]),
            "brave":   ("Brave",   "chromium", [os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History")]),
            "edge":    ("Edge",    "chromium", [os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "History")]),
            "vivaldi": ("Vivaldi", "chromium", [os.path.join(local, "Vivaldi", "User Data", "Default", "History")]),
            "opera":   ("Opera",   "chromium", [os.path.join(roaming, "Opera Software", "Opera Stable", "History")]),
            "firefox": ("Firefox", "firefox",  _firefox_dbs()),
        }
    else:  # Linux
        cfg = os.path.join(home, ".config")
        return {
            "chrome":  ("Chrome",  "chromium", [os.path.join(cfg, "google-chrome", "Default", "History")]),
            "brave":   ("Brave",   "chromium", [os.path.join(cfg, "BraveSoftware", "Brave-Browser", "Default", "History")]),
            "edge":    ("Edge",    "chromium", [os.path.join(cfg, "microsoft-edge", "Default", "History")]),
            "vivaldi": ("Vivaldi", "chromium", [os.path.join(cfg, "vivaldi", "Default", "History")]),
            "opera":   ("Opera",   "chromium", [os.path.join(cfg, "opera", "History")]),
            "firefox": ("Firefox", "firefox",  _firefox_dbs()),
        }


def find_available_browsers() -> list[tuple]:
    """Return list of (key, name, db_type, path) for installed browsers."""
    available = []
    for key, (name, db_type, paths) in _browser_catalog().items():
        for path in paths:
            if os.path.isfile(path):
                available.append((key, name, db_type, path))
                break
    return available


def filter_browsers(available: list, browser_filter: str | None) -> list:
    if not browser_filter:
        return available
    key = browser_filter.strip().lower()
    result = [b for b in available if b[0] == key]
    if not result:
        console.print(f"[red]Browser '{browser_filter}' not found. Run [bold]browser-history browsers[/bold] to list available browsers.[/red]")
    return result


# ---------------------------------------------------------------------------
# DB reading
# ---------------------------------------------------------------------------

def _read_chromium(db_path: str, days: int | None) -> list[dict]:
    try:
        with safe_tmp_copy(db_path) as tmp:
            conn = sqlite3.connect(tmp)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if days:
                cutoff = int(((datetime.now() - timedelta(days=days)) - CHROMIUM_EPOCH).total_seconds() * 1_000_000)
                c.execute(
                    "SELECT u.url, u.title, u.visit_count, v.visit_time, v.visit_duration "
                    "FROM visits v JOIN urls u ON v.url=u.id WHERE v.visit_time>? ORDER BY v.visit_time DESC",
                    (cutoff,)
                )
            else:
                c.execute(
                    "SELECT u.url, u.title, u.visit_count, v.visit_time, v.visit_duration "
                    "FROM visits v JOIN urls u ON v.url=u.id ORDER BY v.visit_time DESC"
                )
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
    except PermissionError:
        console.print("[yellow]  Permission denied — try closing the browser first.[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]  Read error: {type(e).__name__}[/red]")
        return []


def _read_firefox(db_path: str, days: int | None) -> list[dict]:
    try:
        with safe_tmp_copy(db_path) as tmp:
            conn = sqlite3.connect(tmp)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if days:
                cutoff = int(((datetime.now() - timedelta(days=days)) - UNIX_EPOCH).total_seconds() * 1_000_000)
                c.execute(
                    "SELECT p.url, p.title, p.visit_count, v.visit_date "
                    "FROM moz_historyvisits v JOIN moz_places p ON v.place_id=p.id "
                    "WHERE v.visit_date>? ORDER BY v.visit_date DESC",
                    (cutoff,)
                )
            else:
                c.execute(
                    "SELECT p.url, p.title, p.visit_count, v.visit_date "
                    "FROM moz_historyvisits v JOIN moz_places p ON v.place_id=p.id "
                    "ORDER BY v.visit_date DESC"
                )
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
    except PermissionError:
        console.print("[yellow]  Firefox: Permission denied.[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]  Firefox read error: {type(e).__name__}[/red]")
        return []


def _read_safari(db_path: str, days: int | None) -> list[dict]:
    try:
        with safe_tmp_copy(db_path) as tmp:
            conn = sqlite3.connect(tmp)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if days:
                cutoff = ((datetime.now() - timedelta(days=days)) - SAFARI_EPOCH).total_seconds()
                c.execute(
                    "SELECT hi.url, hv.title, hv.visit_time "
                    "FROM history_visits hv JOIN history_items hi ON hv.history_item=hi.id "
                    "WHERE hv.visit_time>? ORDER BY hv.visit_time DESC",
                    (cutoff,)
                )
            else:
                c.execute(
                    "SELECT hi.url, hv.title, hv.visit_time "
                    "FROM history_visits hv JOIN history_items hi ON hv.history_item=hi.id "
                    "ORDER BY hv.visit_time DESC"
                )
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
    except PermissionError:
        console.print(
            "[yellow]  Safari: Permission denied.\n"
            "  System Settings > Privacy & Security > Full Disk Access — add your terminal app.[/yellow]"
        )
        return []
    except Exception as e:
        console.print(f"[red]  Safari read error: {type(e).__name__}[/red]")
        return []


def load_history(browser_key: str, db_type: str, db_path: str, days: int | None) -> list[dict]:
    if db_type == "firefox":
        raw = _read_firefox(db_path, days)
        return [{"url": r.get("url",""), "title": r.get("title",""),
                 "visit_time": unix_ts(r.get("visit_date")),
                 "visit_duration": 0, "visit_count": r.get("visit_count", 1),
                 "browser": browser_key} for r in raw]
    elif db_type == "safari":
        raw = _read_safari(db_path, days)
        return [{"url": r.get("url",""), "title": r.get("title",""),
                 "visit_time": safari_ts(r.get("visit_time")),
                 "visit_duration": 0, "visit_count": 1,
                 "browser": browser_key} for r in raw]
    else:
        raw = _read_chromium(db_path, days)
        return [{"url": r.get("url",""), "title": r.get("title",""),
                 "visit_time": chromium_ts(r.get("visit_time")),
                 "visit_duration": r.get("visit_duration", 0) or 0,
                 "visit_count": r.get("visit_count", 1),
                 "browser": browser_key} for r in raw]


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return url[:50]


def is_internal(url: str) -> bool:
    return not url or any(url.startswith(p) for p in INTERNAL_PREFIXES)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_visits(visits: list[dict]) -> dict:
    domain_stats: dict = defaultdict(lambda: {
        "count": 0, "total_duration": 0, "last_visit": None, "category": None,
    })
    hourly: dict[int, int] = defaultdict(int)
    daily: dict[str, int] = defaultdict(int)
    weekday: dict[int, int] = defaultdict(int)
    category_duration: dict[str, int] = defaultdict(int)
    category_count: dict[str, int] = defaultdict(int)

    for v in visits:
        url = v.get("url", "")
        if is_internal(url):
            continue
        domain = get_domain(url)
        if not domain:
            continue
        cat = categorize(domain)
        dur = v.get("visit_duration", 0) or 0

        domain_stats[domain]["count"] += 1
        domain_stats[domain]["total_duration"] += dur
        domain_stats[domain]["category"] = cat

        category_duration[cat] += dur
        category_count[cat] += 1

        dt = v.get("visit_time")
        if dt:
            lv = domain_stats[domain]["last_visit"]
            if lv is None or dt > lv:
                domain_stats[domain]["last_visit"] = dt
            hourly[dt.hour] += 1
            daily[dt.strftime("%Y-%m-%d")] += 1
            weekday[dt.weekday()] += 1

    return {
        "domain_stats": dict(domain_stats),
        "hourly": dict(hourly),
        "daily": dict(daily),
        "weekday": dict(weekday),
        "category_duration": dict(category_duration),
        "category_count": dict(category_count),
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

DAYS_ABBR = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAYS_KO   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _score_color(score: int) -> str:
    if score >= 70: return "bold green"
    if score >= 40: return "yellow"
    return "red"


def show_summary(visits: list[dict], browser_name: str, result: dict, days: int | None) -> None:
    total = len(visits)
    total_dur = sum(v.get("visit_duration", 0) or 0 for v in visits)
    unique = len(set(get_domain(v["url"]) for v in visits if not is_internal(v.get("url",""))))
    period = f"last {days}d" if days else "all time"

    score = productivity_score(result["category_duration"])
    score_col = _score_color(score)

    times = [v["visit_time"] for v in visits if v.get("visit_time")]
    date_range = ""
    if times:
        date_range = f"{min(times).strftime('%Y-%m-%d')} → {max(times).strftime('%Y-%m-%d')}"

    t = Text()
    t.append("  Visits:           ", "dim")
    t.append(f"{total:,}\n", "bold green")
    t.append("  Unique domains:   ", "dim")
    t.append(f"{unique:,}\n", "bold cyan")
    t.append("  Total time:       ", "dim")
    t.append(f"{duration_str(total_dur)}\n", "bold yellow")
    t.append("  Productivity:     ", "dim")
    t.append(f"{score}/100\n", score_col)
    if date_range:
        t.append("  Period:           ", "dim")
        t.append(date_range, "bold white")

    console.print(Panel(t, title=f"[bold magenta]{browser_name}  ({period})[/bold magenta]", border_style="magenta"))


def show_top_sites(domain_stats: dict, limit: int = 20, sort_by: str = "count") -> None:
    key_fn = (lambda x: x[1]["total_duration"]) if sort_by == "duration" else (lambda x: x[1]["count"])
    items = sorted(domain_stats.items(), key=key_fn, reverse=True)[:limit]

    table = Table(title=f"Top {limit} Sites", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("#",      style="dim",        width=4,  justify="right")
    table.add_column("Domain", style="bold white",  min_width=24)
    table.add_column("Cat",    style="dim",         width=7)
    table.add_column("Visits", justify="right",     style="green")
    table.add_column("Time",   justify="right",     style="yellow")
    table.add_column("Last",   justify="right",     style="blue")

    for i, (domain, s) in enumerate(items, 1):
        cat = s.get("category") or categorize(domain)
        cat_label, cat_color, _ = CATEGORY_META.get(cat, (cat, "dim", 1))
        last = s["last_visit"]
        table.add_row(
            str(i), domain,
            f"[{cat_color}]{cat_label[:6]}[/{cat_color}]",
            f"{s['count']:,}",
            duration_str(s["total_duration"]),
            last.strftime("%m/%d %H:%M") if last else "-",
        )
    console.print(table)


def show_category_breakdown(cat_dur: dict, cat_cnt: dict) -> None:
    total_dur = sum(cat_dur.values()) or 1
    total_cnt = sum(cat_cnt.values()) or 1
    sorted_cats = sorted(cat_dur.items(), key=lambda x: x[1], reverse=True)

    table = Table(title="Category Breakdown", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Category",  min_width=14, style="bold white")
    table.add_column("Time",      justify="right", style="yellow")
    table.add_column("Share",     justify="right", width=7)
    table.add_column("Visits",    justify="right", style="green")
    table.add_column("Bar", min_width=20)

    for cat, dur in sorted_cats:
        label, color, _ = CATEGORY_META.get(cat, (cat, "dim", 1))
        ratio = dur / total_dur
        bar = "█" * int(ratio * 20)
        share = f"{ratio*100:.1f}%"
        cnt = cat_cnt.get(cat, 0)
        table.add_row(
            f"[{color}]{label}[/{color}]",
            duration_str(dur), share,
            f"{cnt:,}",
            f"[{color}]{bar}[/{color}]",
        )
    console.print(table)


def show_hourly_heatmap(hourly: dict) -> None:
    if not hourly:
        return
    mx = max(hourly.values())
    blocks = ["░", "▒", "▓", "█"]
    console.print("\n[bold cyan]Hourly pattern[/bold cyan]")
    console.print("[dim]0h                     12h                    23h[/dim]")
    bar = ""
    for h in range(24):
        r = hourly.get(h, 0) / mx if mx else 0
        blk = blocks[int(r * (len(blocks) - 1))]
        if r == 0:
            bar += f"[dim]{blk}[/dim]"
        elif r < 0.33:
            bar += f"[blue]{blk}[/blue]"
        elif r < 0.66:
            bar += f"[yellow]{blk}[/yellow]"
        else:
            bar += f"[red]{blk}[/red]"
    console.print(bar)
    peaks = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:3]
    console.print("  Peak: " + ", ".join(f"[bold]{h}:00[/bold]({c:,})" for h, c in peaks))


def show_weekday_chart(weekday: dict) -> None:
    if not weekday:
        return
    mx = max(weekday.values()) or 1
    console.print("\n[bold cyan]Day of week[/bold cyan]")
    for wd in range(7):
        cnt = weekday.get(wd, 0)
        r = cnt / mx
        bar = "█" * int(r * 28)
        color = "magenta" if wd >= 5 else "green"
        console.print(f"  {DAYS_ABBR[wd]} [{color}]{bar:<28}[/{color}] {cnt:,}")


def show_calendar_heatmap(daily: dict, weeks: int = 24) -> None:
    """GitHub-style contribution calendar."""
    if not daily:
        return

    today = datetime.now().date()
    # Align start to Monday
    start = (today - timedelta(weeks=weeks))
    start = start - timedelta(days=start.weekday())

    all_counts = list(daily.values())
    mx = max(all_counts) if all_counts else 1
    p25 = sorted(all_counts)[int(len(all_counts) * 0.25)] if all_counts else 1
    p50 = sorted(all_counts)[int(len(all_counts) * 0.50)] if all_counts else 1
    p75 = sorted(all_counts)[int(len(all_counts) * 0.75)] if all_counts else 1

    def cell(date_str: str) -> str:
        c = daily.get(date_str, 0)
        if c == 0:
            return "[dim]░[/dim]"
        elif c <= p25:
            return "[blue]▒[/blue]"
        elif c <= p50:
            return "[cyan]▒[/cyan]"
        elif c <= p75:
            return "[green]▓[/green]"
        else:
            return "[bold green]█[/bold green]"

    # Month labels row
    month_row = "      "
    col_dates = []
    d = start
    while d <= today:
        col_dates.append(d)
        d += timedelta(weeks=1)

    prev_month = -1
    for d in col_dates:
        if d.month != prev_month:
            lbl = d.strftime("%b")
            month_row += lbl[:3] + " "
            prev_month = d.month
        else:
            month_row += "    "

    console.print(f"\n[bold cyan]Activity calendar (last {weeks} weeks)[/bold cyan]")
    console.print(f"[dim]{month_row}[/dim]")

    for wd in range(7):
        row = f"  {DAYS_ABBR[wd]} "
        d = start + timedelta(days=wd)
        while d <= today:
            row += cell(d.strftime("%Y-%m-%d")) + "  "
            d += timedelta(weeks=1)
        console.print(row)

    # Legend
    console.print("[dim]  Low [blue]▒[/blue] [cyan]▒[/cyan] [green]▓[/green] [bold green]█[/bold green] High[/dim]")


def show_daily_trend(daily: dict, n: int = 14) -> None:
    if not daily:
        return
    items = sorted(daily.items())[-n:]
    mx = max(c for _, c in items) or 1
    console.print(f"\n[bold cyan]Last {n} days[/bold cyan]")
    for ds, cnt in items:
        try:
            dt = datetime.strptime(ds, "%Y-%m-%d")
            label = dt.strftime("%m/%d")
            wd = DAYS_ABBR[dt.weekday()]
            color = "magenta" if dt.weekday() >= 5 else "cyan"
        except Exception:
            label, wd, color = ds[-5:], "  ", "cyan"
        bar = "█" * int((cnt / mx) * 24)
        console.print(f"  {label}({wd}) [{color}]{bar:<24}[/{color}] {cnt:,}")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _visits_to_rows(visits: list[dict]) -> list[dict]:
    rows = []
    for v in visits:
        url = v.get("url", "")
        if is_internal(url):
            continue
        dt = v.get("visit_time")
        rows.append({
            "timestamp":  dt.isoformat() if dt else "",
            "url":        url,
            "domain":     get_domain(url),
            "category":   categorize(get_domain(url)),
            "title":      v.get("title", ""),
            "duration_s": round((v.get("visit_duration", 0) or 0) / 1_000_000, 2),
            "browser":    v.get("browser", ""),
        })
    return rows


def export_csv(visits: list[dict], path: str | None) -> None:
    rows = _visits_to_rows(visits)
    fields = ["timestamp", "url", "domain", "category", "title", "duration_s", "browser"]
    if path:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        console.print(f"[green]Exported {len(rows):,} rows → {path}[/green]")
    else:
        buf = StringIO()
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        print(buf.getvalue())


def export_json(visits: list[dict], path: str | None, result: dict) -> None:
    rows = _visits_to_rows(visits)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_visits": len(visits),
            "unique_domains": len(set(r["domain"] for r in rows)),
            "total_duration_s": sum(r["duration_s"] for r in rows),
            "category_duration_s": {k: round(v / 1_000_000, 2) for k, v in result["category_duration"].items()},
            "productivity_score": productivity_score(result["category_duration"]),
        },
        "visits": rows,
    }
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        console.print(f"[green]Exported {len(rows):,} records → {path}[/green]")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def export_html(visits: list[dict], path: str, result: dict) -> None:
    rows = _visits_to_rows(visits)
    top20 = sorted(
        result["domain_stats"].items(),
        key=lambda x: x[1]["count"], reverse=True
    )[:20]
    top_labels = json.dumps([d for d, _ in top20])
    top_visits = json.dumps([s["count"] for _, s in top20])
    top_times  = json.dumps([round(s["total_duration"] / 3_600_000_000, 2) for _, s in top20])

    cat_labels = json.dumps(list(result["category_duration"].keys()))
    cat_values = json.dumps([round(v / 3_600_000_000, 2) for v in result["category_duration"].values()])

    hourly_labels = json.dumps(list(range(24)))
    hourly_values = json.dumps([result["hourly"].get(h, 0) for h in range(24)])

    score = productivity_score(result["category_duration"])
    total_dur = sum(result["category_duration"].values())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Browser History Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0d1117; color: #c9d1d9; padding: 24px; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 8px; color: #58a6ff; }}
  .sub {{ color: #8b949e; font-size: .85rem; margin-bottom: 32px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
  .card .val {{ font-size: 2rem; font-weight: 700; color: #58a6ff; }}
  .card .lbl {{ font-size: .8rem; color: #8b949e; margin-top: 4px; }}
  .score-{{"green" if score >= 70 else "yellow" if score >= 40 else "red"}} {{ color: {"#3fb950" if score >= 70 else "#d29922" if score >= 40 else "#f85149"} !important; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
  .chart-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
  .chart-box h2 {{ font-size: 1rem; margin-bottom: 16px; color: #8b949e; }}
  canvas {{ max-height: 320px; }}
  @media(max-width: 700px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .footer {{ text-align: center; color: #8b949e; font-size: .75rem; margin-top: 32px; }}
</style>
</head>
<body>
<h1>Browser History Report</h1>
<div class="sub">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} &nbsp;|&nbsp; {len(rows):,} visits</div>
<div class="grid">
  <div class="card"><div class="val">{len(rows):,}</div><div class="lbl">Total visits</div></div>
  <div class="card"><div class="val">{len(set(r["domain"] for r in rows)):,}</div><div class="lbl">Unique domains</div></div>
  <div class="card"><div class="val">{round(total_dur/3_600_000_000, 1)}h</div><div class="lbl">Total time</div></div>
  <div class="card"><div class="val score-{("green" if score>=70 else "yellow" if score>=40 else "red")}">{score}</div><div class="lbl">Productivity score</div></div>
</div>
<div class="charts">
  <div class="chart-box"><h2>Top 20 Sites — Visits</h2><canvas id="c1"></canvas></div>
  <div class="chart-box"><h2>Top 20 Sites — Time (hours)</h2><canvas id="c2"></canvas></div>
  <div class="chart-box"><h2>Hourly Pattern</h2><canvas id="c3"></canvas></div>
  <div class="chart-box"><h2>Category Breakdown (hours)</h2><canvas id="c4"></canvas></div>
</div>
<div class="footer">browser-history-cli — data processed locally, never uploaded</div>
<script>
const cfg = (ctx, type, labels, data, label, color) => new Chart(ctx, {{
  type, data: {{ labels, datasets: [{{ label, data, backgroundColor: color,
    borderColor: color, borderWidth: type==='line'?2:0, fill: false }}] }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
    scales: type!=='pie' ? {{ x: {{ ticks: {{ color:'#8b949e', font:{{size:10}} }}, grid:{{color:'#21262d'}} }},
      y: {{ ticks: {{ color:'#8b949e' }}, grid:{{color:'#21262d'}} }} }} : {{}} }} }});
cfg(document.getElementById('c1'),'bar',{top_labels},{top_visits},'Visits','#58a6ff');
cfg(document.getElementById('c2'),'bar',{top_labels},{top_times},'Hours','#3fb950');
cfg(document.getElementById('c3'),'bar',{hourly_labels},{hourly_values},'Visits','#d29922');
cfg(document.getElementById('c4'),'pie',{cat_labels},{cat_values},'Hours',
  ['#58a6ff','#3fb950','#f85149','#d29922','#a371f7','#39d353','#8b949e','#ffa657','#79c0ff','#56d364']);
</script>
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    console.print(f"[green]HTML report → {path}[/green]")
    console.print(f"[dim]Open with: open {path}[/dim]" if SYSTEM == "Darwin" else
                  f"[dim]Open with: start {path}[/dim]" if SYSTEM == "Windows" else
                  f"[dim]Open with: xdg-open {path}[/dim]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_stats(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    for bkey, bname, btype, bpath in available:
        console.print(f"\n[bold blue]>>> {bname}[/bold blue]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            t = p.add_task("Loading history…")
            visits = load_history(bkey, btype, bpath, args.days)
            p.update(t, completed=True)

        if not visits:
            console.print("[yellow]  No history found.[/yellow]"); continue

        result = analyze_visits(visits)
        show_summary(visits, bname, result, args.days)
        show_top_sites(result["domain_stats"], args.top, args.sort)
        show_category_breakdown(result["category_duration"], result["category_count"])
        show_hourly_heatmap(result["hourly"])
        show_weekday_chart(result["weekday"])
        show_calendar_heatmap(result["daily"])
        show_daily_trend(result["daily"], n=min(14, args.days or 14))


def cmd_top(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        all_visits.extend(load_history(bkey, btype, bpath, args.days))
    if not all_visits:
        console.print("[yellow]No history found.[/yellow]"); return

    result = analyze_visits(all_visits)
    period = f"last {args.days}d" if args.days else "all time"
    console.print(f"\n[bold magenta]{args.browser or 'All browsers'}  |  {period}[/bold magenta]")
    show_top_sites(result["domain_stats"], args.limit, args.sort)


def cmd_search(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    keyword = args.keyword
    try:
        pattern = re.compile(keyword, re.IGNORECASE) if args.regex else None
    except re.error as e:
        console.print(f"[red]Invalid regex: {e}[/red]"); return

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        all_visits.extend(load_history(bkey, btype, bpath, args.days))

    def matches(v: dict) -> bool:
        url   = v.get("url", "")
        title = v.get("title", "") or ""
        fields = []
        if args.field in ("url", "both"):   fields.append(url)
        if args.field in ("title", "both"): fields.append(title)
        if pattern:
            return any(pattern.search(f) for f in fields)
        kw = keyword.lower()
        return any(kw in f.lower() for f in fields)

    hits = [v for v in all_visits if not is_internal(v.get("url","")) and matches(v)]
    hits = sorted(hits, key=lambda v: v.get("visit_time") or datetime.min, reverse=True)[:args.limit]

    if not hits:
        console.print(f"[yellow]No results for '{keyword}'.[/yellow]"); return

    table = Table(title=f"Search: '{keyword}'  ({len(hits)} results)", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Time",   style="blue",  width=16)
    table.add_column("Domain", style="bold white", min_width=18)
    table.add_column("Title",  style="white", min_width=28, max_width=48)
    table.add_column("Dur",    justify="right", style="yellow")

    for v in hits:
        dt = v.get("visit_time")
        title = (v.get("title") or "")[:48]
        table.add_row(
            dt.strftime("%Y-%m-%d %H:%M") if dt else "-",
            get_domain(v.get("url", "")),
            title,
            duration_str(v.get("visit_duration", 0)),
        )
    console.print(table)


def cmd_export(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        all_visits.extend(load_history(bkey, btype, bpath, args.days))
    if not all_visits:
        console.print("[yellow]No history found.[/yellow]"); return

    result = analyze_visits(all_visits)
    fmt = args.format.lower()
    out = args.output

    if fmt == "csv":
        export_csv(all_visits, out)
    elif fmt == "json":
        export_json(all_visits, out, result)
    elif fmt == "html":
        if not out:
            out = "browser_history_report.html"
        export_html(all_visits, out, result)
    else:
        console.print(f"[red]Unknown format: {fmt}[/red]")


def cmd_category(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        all_visits.extend(load_history(bkey, btype, bpath, args.days))
    if not all_visits:
        console.print("[yellow]No history found.[/yellow]"); return

    result = analyze_visits(all_visits)
    period = f"last {args.days}d" if args.days else "all time"
    console.print(f"\n[bold magenta]{args.browser or 'All browsers'}  |  {period}[/bold magenta]")
    show_category_breakdown(result["category_duration"], result["category_count"])

    score = productivity_score(result["category_duration"])
    col = _score_color(score)
    console.print(f"\n  Productivity score: [{col}]{score}/100[/{col}]")

    if args.detail:
        for cat in sorted(result["category_duration"], key=lambda k: result["category_duration"][k], reverse=True):
            label, color, _ = CATEGORY_META.get(cat, (cat, "dim", 1))
            sites = [
                (d, s) for d, s in result["domain_stats"].items()
                if s.get("category") == cat
            ]
            if not sites:
                continue
            top = sorted(sites, key=lambda x: x[1]["count"], reverse=True)[:5]
            console.print(f"\n  [{color}]{label}[/{color}]")
            for domain, s in top:
                console.print(f"    {domain:<30} {s['count']:>6} visits  {duration_str(s['total_duration']):>8}")


def cmd_today(args) -> None:
    args.days = 1
    args.sort = "count"
    args.top = 15
    cmd_stats(args)


def cmd_week(args) -> None:
    args.days = 7
    args.sort = "count"
    args.top = 20
    cmd_stats(args)


def cmd_list_browsers(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print(f"[red]No browsers found on {SYSTEM}.[/red]"); return

    table = Table(title=f"Detected browsers ({SYSTEM})", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Key",     style="yellow")
    table.add_column("Browser", style="bold white")
    table.add_column("Type",    style="dim")
    table.add_column("DB path", style="dim")

    for key, name, db_type, path in available:
        table.add_row(key, name, db_type, path)

    console.print(table)
    console.print("\n[dim]Usage: [bold]browser-history stats --browser <key>[/bold][/dim]")


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def generate_insights(visits: list[dict], result: dict) -> list[str]:
    """Derive human-readable behavioral observations from visit data."""
    insights: list[str] = []
    domain_stats = result["domain_stats"]
    hourly       = result["hourly"]
    daily        = result["daily"]
    weekday      = result["weekday"]
    cat_dur      = result["category_duration"]

    if not visits or not domain_stats:
        return ["Not enough data — try running without [bold]--days[/bold] to include all history."]

    # Top site
    top_dom, top_s = max(domain_stats.items(), key=lambda x: x[1]["count"])
    cat_label = CATEGORY_META.get(top_s.get("category", "other"), ("Other", "dim", 1))[0]
    insights.append(
        f"[dim]→[/dim] Most visited: [bold cyan]{top_dom}[/bold cyan]"
        f"  ({top_s['count']:,} visits · {cat_label})"
    )

    # Peak hour
    if hourly:
        ph, pc = max(hourly.items(), key=lambda x: x[1])
        ampm = f"{ph % 12 or 12}{'am' if ph < 12 else 'pm'}"
        insights.append(f"[dim]→[/dim] Peak browsing hour: [bold cyan]{ampm}[/bold cyan]  ({pc:,} visits)")

    # Most active period of day
    if hourly:
        periods = {
            "morning (6–12)":   sum(hourly.get(h, 0) for h in range(6, 12)),
            "afternoon (12–18)": sum(hourly.get(h, 0) for h in range(12, 18)),
            "evening (18–22)":  sum(hourly.get(h, 0) for h in range(18, 22)),
            "night (22–6)":     sum(hourly.get(h, 0) for h in list(range(22, 24)) + list(range(0, 6))),
        }
        peak_period = max(periods.items(), key=lambda x: x[1])
        insights.append(f"[dim]→[/dim] Most active period: [bold]{peak_period[0]}[/bold]  ({peak_period[1]:,} visits)")

    # Weekend vs weekday
    wd_avg = sum(weekday.get(d, 0) for d in range(5)) / 5 if weekday else 0
    we_avg = sum(weekday.get(d, 0) for d in range(5, 7)) / 2 if weekday else 0
    if wd_avg > 0 and we_avg > 0:
        ratio = we_avg / wd_avg
        if ratio > 1.3:
            insights.append(f"[dim]→[/dim] You browse [bold]{ratio:.1f}×[/bold] more on weekends than weekdays")
        elif ratio < 0.7:
            insights.append(
                f"[dim]→[/dim] Focused weekday browser — [bold]{wd_avg/we_avg:.1f}×[/bold] more active than weekends"
            )

    # Biggest leisure sink
    leisure = {k: v for k, v in cat_dur.items() if CATEGORY_META.get(k, ("", "", 1))[2] == 0}
    if leisure:
        lk, lv = max(leisure.items(), key=lambda x: x[1])
        insights.append(
            f"[dim]→[/dim] Biggest leisure sink: [bold]{CATEGORY_META.get(lk, ('Other','dim',1))[0]}[/bold]"
            f"  ({duration_str(lv)} spent)"
        )

    # Busiest day
    if daily:
        bd, bc = max(daily.items(), key=lambda x: x[1])
        try:
            dt = datetime.strptime(bd, "%Y-%m-%d")
            insights.append(
                f"[dim]→[/dim] Busiest day: [bold cyan]{bd} ({DAYS_KO[dt.weekday()]})[/bold cyan]"
                f"  — {bc:,} visits"
            )
        except Exception:
            pass

    # Daily average + consecutive streak
    if daily:
        active_days = len(daily)
        avg = sum(daily.values()) / active_days
        insights.append(
            f"[dim]→[/dim] Daily average: [bold]{avg:.0f}[/bold] visits across {active_days} active days"
        )
        streak = 0
        d = datetime.now().date()
        while d.strftime("%Y-%m-%d") in daily:
            streak += 1
            d -= timedelta(days=1)
        if streak > 1:
            insights.append(f"[dim]→[/dim] Active streak: [bold green]{streak} consecutive days[/bold green]")

    # Morning routine (6–10am top domains)
    morning = [
        v for v in visits
        if v.get("visit_time") and 6 <= v["visit_time"].hour <= 10
        and not is_internal(v.get("url", ""))
    ]
    if len(morning) >= 5:
        mc: dict[str, int] = defaultdict(int)
        for v in morning:
            mc[get_domain(v["url"])] += 1
        top_m = sorted(mc.items(), key=lambda x: x[1], reverse=True)[:3]
        routine = " → ".join(d for d, _ in top_m)
        insights.append(f"[dim]→[/dim] Morning routine (6–10am): [bold]{routine}[/bold]")

    # Unique domains
    insights.append(f"[dim]→[/dim] Explored [bold]{len(domain_stats):,}[/bold] unique domains")

    # Productivity interpretation
    score = productivity_score(cat_dur)
    if score >= 70:
        insights.append(f"[dim]→[/dim] Productivity: [bold green]{score}/100[/bold green]  — impressive focus")
    elif score >= 40:
        insights.append(f"[dim]→[/dim] Productivity: [bold yellow]{score}/100[/bold yellow]  — balanced browsing")
    else:
        insights.append(f"[dim]→[/dim] Productivity: [bold red]{score}/100[/bold red]  — heavy leisure time")

    return insights


def cmd_insights(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
            t = p.add_task(f"Loading {bname}…")
            all_visits.extend(load_history(bkey, btype, bpath, args.days))
            p.update(t, completed=True)

    if not all_visits:
        console.print("[yellow]No history found.[/yellow]"); return

    result = analyze_visits(all_visits)
    period = f"last {args.days}d" if args.days else "all time"
    lines  = generate_insights(all_visits, result)

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold magenta]Insights — {args.browser or 'All browsers'} · {period}[/bold magenta]",
        border_style="magenta",
        padding=(1, 2),
    ))


# ---------------------------------------------------------------------------
# Compare command
# ---------------------------------------------------------------------------

def _pct_delta(a: float, b: float) -> str:
    if a == 0:
        return "[dim]n/a[/dim]"
    pct = (b - a) / a * 100
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    return f"[{color}]{sign}{pct:.0f}%[/{color}]"


def cmd_compare(args) -> None:
    """Compare two consecutive time periods side-by-side."""
    period_map = {"week": (7, "week"), "month": (30, "month")}
    period_days, period_label = period_map[args.period]

    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    now     = datetime.now()
    end_b   = now
    start_b = now - timedelta(days=period_days)
    end_a   = start_b
    start_a = end_a - timedelta(days=period_days)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        t = p.add_task("Loading history for both periods…")
        all_visits: list[dict] = []
        for bkey, bname, btype, bpath in available:
            all_visits.extend(load_history(bkey, btype, bpath, period_days * 2))
        p.update(t, completed=True)

    def _slice(start: datetime, end: datetime) -> list[dict]:
        return [v for v in all_visits if v.get("visit_time") and start <= v["visit_time"] <= end]

    visits_a = _slice(start_a, end_a)
    visits_b = _slice(start_b, end_b)

    if not visits_a and not visits_b:
        console.print("[yellow]Not enough history to compare.[/yellow]"); return

    res_a = analyze_visits(visits_a)
    res_b = analyze_visits(visits_b)

    score_a  = productivity_score(res_a["category_duration"])
    score_b  = productivity_score(res_b["category_duration"])
    unique_a = len(res_a["domain_stats"])
    unique_b = len(res_b["domain_stats"])
    total_a  = len(visits_a)
    total_b  = len(visits_b)
    dur_a    = sum(v.get("visit_duration", 0) or 0 for v in visits_a)
    dur_b    = sum(v.get("visit_duration", 0) or 0 for v in visits_b)
    top_a    = max(res_a["domain_stats"], key=lambda d: res_a["domain_stats"][d]["count"]) if res_a["domain_stats"] else "—"
    top_b    = max(res_b["domain_stats"], key=lambda d: res_b["domain_stats"][d]["count"]) if res_b["domain_stats"] else "—"

    label_a = f"Last {period_label}"
    label_b = f"This {period_label}"

    table = Table(
        title=f"[bold]{label_a}[/bold] vs [bold]{label_b}[/bold]",
        box=box.ROUNDED, header_style="bold cyan",
    )
    table.add_column("Metric",       style="dim",        min_width=18)
    table.add_column(label_a,        style="white",      justify="right", min_width=14)
    table.add_column(label_b,        style="bold white", justify="right", min_width=14)
    table.add_column("Change",       justify="right",    min_width=8)

    table.add_row("Total visits",   f"{total_a:,}",      f"{total_b:,}",       _pct_delta(total_a,  total_b))
    table.add_row("Unique domains", f"{unique_a:,}",     f"{unique_b:,}",      _pct_delta(unique_a, unique_b))
    table.add_row("Total time",     duration_str(dur_a), duration_str(dur_b),  _pct_delta(dur_a,    dur_b))
    table.add_row("Productivity",   f"{score_a}/100",    f"{score_b}/100",     _pct_delta(score_a,  score_b))
    table.add_row("Top site",       top_a,               top_b,                "")

    console.print(table)

    doms_a = set(res_a["domain_stats"])
    doms_b = set(res_b["domain_stats"])
    new_doms  = sorted(doms_b - doms_a, key=lambda d: res_b["domain_stats"][d]["count"], reverse=True)[:5]
    lost_doms = sorted(doms_a - doms_b, key=lambda d: res_a["domain_stats"][d]["count"], reverse=True)[:5]

    if new_doms:
        console.print(f"\n[green]New this {period_label}:[/green]  " + "  ".join(f"[bold]{d}[/bold]" for d in new_doms))
    if lost_doms:
        console.print(f"[dim]No longer visited:[/dim]  " + "  ".join(lost_doms))

    common = doms_a & doms_b
    if common:
        movers = [
            (d, res_a["domain_stats"][d]["count"], res_b["domain_stats"][d]["count"],
             (res_b["domain_stats"][d]["count"] - res_a["domain_stats"][d]["count"]) / max(res_a["domain_stats"][d]["count"], 1))
            for d in common
        ]
        gainers = sorted([(d, ca, cb, p) for d, ca, cb, p in movers if p >= 0.25],  key=lambda x: x[3], reverse=True)[:3]
        losers  = sorted([(d, ca, cb, p) for d, ca, cb, p in movers if p <= -0.25], key=lambda x: x[3])[:3]

        if gainers:
            console.print(f"\n[green]Biggest increases:[/green]")
            for d, ca, cb, pct in gainers:
                console.print(f"  [bold]{d:<32}[/bold] {ca:>5} → {cb:>5}  [green]+{pct*100:.0f}%[/green]")
        if losers:
            console.print(f"\n[red]Biggest decreases:[/red]")
            for d, ca, cb, pct in losers:
                console.print(f"  [bold]{d:<32}[/bold] {ca:>5} → {cb:>5}  [red]{pct*100:.0f}%[/red]")


# ---------------------------------------------------------------------------
# Timeline command
# ---------------------------------------------------------------------------

def show_timeline(visits: list[dict], target_date) -> None:
    """Render an hour-by-hour browsing activity chart for a given date."""
    day_visits = [
        v for v in visits
        if v.get("visit_time") and v["visit_time"].date() == target_date
        and not is_internal(v.get("url", ""))
    ]

    date_str = target_date.strftime("%Y-%m-%d")
    if not day_visits:
        console.print(f"[yellow]No activity found for {date_str}.[/yellow]"); return

    by_hour: dict[int, list] = defaultdict(list)
    for v in day_visits:
        by_hour[v["visit_time"].hour].append(v)

    mx    = max(len(vv) for vv in by_hour.values())
    total = len(day_visits)

    try:
        dt      = datetime.strptime(date_str, "%Y-%m-%d")
        day_lbl = f"({DAYS_KO[dt.weekday()]})"
    except Exception:
        day_lbl = ""

    console.print(f"\n[bold cyan]Activity Timeline — {date_str} {day_lbl}[/bold cyan]  [dim]{total:,} visits[/dim]")

    for h in range(24):
        vv = by_hour.get(h, [])
        n  = len(vv)

        if n == 0:
            console.print(f"  [dim]{h:02d}:00   ·[/dim]")
            continue

        bar_len = max(1, int((n / mx) * 24))
        if   6  <= h < 9:  color = "cyan"
        elif 9  <= h < 12: color = "green"
        elif 12 <= h < 14: color = "yellow"
        elif 14 <= h < 18: color = "green"
        elif 18 <= h < 22: color = "blue"
        else:              color = "magenta"

        bar = f"[{color}]{'█' * bar_len}[/{color}]"

        dc: dict[str, int] = defaultdict(int)
        for v in vv:
            dc[get_domain(v.get("url", ""))] += 1
        top_d = sorted(dc.items(), key=lambda x: x[1], reverse=True)[:4]
        doms  = "  ".join(
            f"[dim]{d}[/dim][bright_black]×{c}[/bright_black]" if c > 1 else f"[dim]{d}[/dim]"
            for d, c in top_d
        )
        console.print(f"  [bold]{h:02d}:00[/bold]  [dim]{n:3}[/dim]  {bar:<26}  {doms}")


def cmd_timeline(args) -> None:
    available = find_available_browsers()
    if not available:
        console.print("[red]No browsers found.[/red]"); return
    available = filter_browsers(available, args.browser)
    if not available:
        return

    if args.date:
        try:
            target = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            console.print("[red]Invalid date — use YYYY-MM-DD format.[/red]"); return
        days_back = (datetime.now().date() - target).days + 1
        if days_back < 1:
            console.print("[red]Date cannot be in the future.[/red]"); return
    else:
        target    = datetime.now().date()
        days_back = 1

    all_visits: list[dict] = []
    for bkey, bname, btype, bpath in available:
        all_visits.extend(load_history(bkey, btype, bpath, days_back))

    show_timeline(all_visits, target)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="browser-history",
        description="Browser History Analyzer — macOS / Windows / Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  browser-history stats                        # full stats for all browsers
  browser-history stats --browser chrome -d 7  # Chrome, last 7 days
  browser-history today                        # quick look at today
  browser-history week                         # this week's summary
  browser-history insights                     # smart behavioral insights (last 30d)
  browser-history insights --days 7            # insights for the last 7 days
  browser-history compare                      # this week vs last week
  browser-history compare --period month       # this month vs last month
  browser-history timeline                     # hour-by-hour view of today
  browser-history timeline --date 2024-03-10   # activity for a specific day
  browser-history top --sort duration -l 30    # top 30 by time spent
  browser-history search "github" --days 30    # search history
  browser-history category --detail --days 7   # category breakdown
  browser-history export --format html -o report.html
  browser-history export --format csv  -o history.csv
  browser-history export --format json | jq .summary
  browser-history browsers                     # list detected browsers
        """,
    )

    sub = parser.add_subparsers(dest="command")

    # ---- stats ----
    p = sub.add_parser("stats", help="Full statistics dashboard")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days", "-d", type=positive_int, default=None, metavar="N")
    p.add_argument("--top",  "-t", type=positive_int, default=20,   metavar="N")
    p.add_argument("--sort", "-s", choices=["count", "duration"], default="count")

    # ---- top ----
    p = sub.add_parser("top", help="Top sites ranking")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days",  "-d", type=positive_int, default=None, metavar="N")
    p.add_argument("--limit", "-l", type=positive_int, default=20,   metavar="N")
    p.add_argument("--sort",  "-s", choices=["count", "duration"], default="count")

    # ---- search ----
    p = sub.add_parser("search", help="Search history by keyword")
    p.add_argument("keyword")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days",  "-d", type=positive_int, default=None, metavar="N")
    p.add_argument("--limit", "-l", type=positive_int, default=50,   metavar="N")
    p.add_argument("--field", "-f", choices=["url", "title", "both"], default="both")
    p.add_argument("--regex", "-r", action="store_true", help="Treat keyword as regex")

    # ---- export ----
    p = sub.add_parser("export", help="Export history to CSV / JSON / HTML")
    p.add_argument("--format", "-f", choices=["csv", "json", "html"], default="csv")
    p.add_argument("--output", "-o", metavar="FILE", default=None)
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days",  "-d", type=positive_int, default=None, metavar="N")

    # ---- category ----
    p = sub.add_parser("category", help="Category & productivity analysis")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days",  "-d", type=positive_int, default=None, metavar="N")
    p.add_argument("--detail", action="store_true", help="Show top sites per category")

    # ---- today / week ----
    for cmd_name in ("today", "week"):
        p = sub.add_parser(cmd_name, help=f"Quick summary for {'today' if cmd_name=='today' else 'this week'}")
        p.add_argument("--browser", "-b", metavar="BROWSER")

    # ---- browsers ----
    sub.add_parser("browsers", help="List detected browsers")

    # ---- insights ----
    p = sub.add_parser("insights", help="Smart behavioral insights from your browsing history")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--days", "-d", type=positive_int, default=30, metavar="N",
                   help="Days to analyze (default: 30)")

    # ---- compare ----
    p = sub.add_parser("compare", help="Compare this period vs last period")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--period", choices=["week", "month"], default="week",
                   help="Comparison window: week (7d) or month (30d) (default: week)")

    # ---- timeline ----
    p = sub.add_parser("timeline", help="Hour-by-hour activity for a specific day")
    p.add_argument("--browser", "-b", metavar="BROWSER")
    p.add_argument("--date", "-d", metavar="YYYY-MM-DD", default=None,
                   help="Date to display (default: today)")

    args = parser.parse_args()

    dispatch = {
        "stats":    cmd_stats,
        "top":      cmd_top,
        "search":   cmd_search,
        "export":   cmd_export,
        "category": cmd_category,
        "today":    cmd_today,
        "week":     cmd_week,
        "browsers": cmd_list_browsers,
        "insights": cmd_insights,
        "compare":  cmd_compare,
        "timeline": cmd_timeline,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        # Default: stats for all browsers
        args.browser = None
        args.days    = None
        args.top     = 20
        args.sort    = "count"
        cmd_stats(args)


if __name__ == "__main__":
    main()
