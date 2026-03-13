#!/usr/bin/env python3
"""
브라우저 방문 기록 분석 CLI
지원 브라우저: Arc, Chrome, Brave, Edge, Vivaldi, Opera, Firefox, Safari
지원 OS: macOS, Windows, Linux
"""

import argparse
import sqlite3
import shutil
import tempfile
import os
import sys
import glob
import platform
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
except ImportError:
    print("rich 라이브러리가 필요합니다: pip install rich")
    sys.exit(1)

console = Console()

SYSTEM = platform.system()  # 'Darwin' | 'Windows' | 'Linux'

# 브라우저 내부 URL 접두사 (분석에서 제외)
INTERNAL_PREFIXES = (
    "chrome://", "arc://", "about:", "moz-extension://",
    "chrome-extension://", "edge://", "brave://", "vivaldi://",
    "opera://", "file://",
)

# --------------------------------------------------------------------------- #
# 시간 변환
# --------------------------------------------------------------------------- #
CHROMIUM_EPOCH = datetime(1601, 1, 1)
UNIX_EPOCH = datetime(1970, 1, 1)
SAFARI_EPOCH = datetime(2001, 1, 1)


def chromium_ts_to_dt(microseconds):
    if not microseconds:
        return None
    try:
        return CHROMIUM_EPOCH + timedelta(microseconds=microseconds)
    except (OverflowError, OSError):
        return None


def unix_ts_to_dt(microseconds):
    if not microseconds:
        return None
    try:
        return UNIX_EPOCH + timedelta(microseconds=microseconds)
    except (OverflowError, OSError):
        return None


def safari_ts_to_dt(seconds):
    if not seconds:
        return None
    try:
        return SAFARI_EPOCH + timedelta(seconds=seconds)
    except (OverflowError, OSError):
        return None


def duration_to_str(microseconds):
    if not microseconds or microseconds <= 0:
        return "-"
    seconds = microseconds / 1_000_000
    if seconds < 60:
        return f"{seconds:.0f}초"
    elif seconds < 3600:
        return f"{seconds/60:.1f}분"
    else:
        return f"{seconds/3600:.1f}시간"


# --------------------------------------------------------------------------- #
# OS별 브라우저 경로 정의
# --------------------------------------------------------------------------- #

def _find_firefox_db():
    """Firefox 프로파일 디렉터리에서 places.sqlite 를 찾아 반환."""
    home = os.path.expanduser("~")
    if SYSTEM == "Darwin":
        base = os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")
    elif SYSTEM == "Windows":
        base = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")
    else:  # Linux
        base = os.path.join(home, ".mozilla", "firefox")

    if not os.path.isdir(base):
        return []

    # default-release 프로파일 우선, 없으면 places.sqlite 가 있는 첫 번째 디렉터리
    candidates = []
    for entry in os.listdir(base):
        profile_dir = os.path.join(base, entry)
        db = os.path.join(profile_dir, "places.sqlite")
        if os.path.isfile(db):
            if "default-release" in entry or "default" in entry:
                candidates.insert(0, db)
            else:
                candidates.append(db)
    return candidates


def _arc_windows_paths():
    """Windows Store 앱으로 설치된 Arc 경로 (패키지 해시가 달라 glob 사용)."""
    local = os.environ.get("LOCALAPPDATA", "")
    pattern = os.path.join(
        local, "Packages", "TheBrowserCompany.Arc_*",
        "LocalCache", "Local", "Arc", "User Data", "Default", "History"
    )
    return glob.glob(pattern)


def build_browser_catalog():
    """현재 OS에 맞는 브라우저 경로 딕셔너리 반환."""
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA", "")   # Windows only
    roaming = os.environ.get("APPDATA", "")       # Windows only

    if SYSTEM == "Darwin":
        sup = os.path.join(home, "Library", "Application Support")
        catalog = {
            "arc":     {"name": "Arc",     "type": "chromium", "paths": [
                os.path.join(sup, "Arc", "User Data", "Default", "History"),
            ]},
            "chrome":  {"name": "Chrome",  "type": "chromium", "paths": [
                os.path.join(sup, "Google", "Chrome", "Default", "History"),
            ]},
            "brave":   {"name": "Brave",   "type": "chromium", "paths": [
                os.path.join(sup, "BraveSoftware", "Brave-Browser", "Default", "History"),
            ]},
            "edge":    {"name": "Edge",    "type": "chromium", "paths": [
                os.path.join(sup, "Microsoft Edge", "Default", "History"),
            ]},
            "vivaldi": {"name": "Vivaldi", "type": "chromium", "paths": [
                os.path.join(sup, "Vivaldi", "Default", "History"),
            ]},
            "opera":   {"name": "Opera",   "type": "chromium", "paths": [
                os.path.join(sup, "com.operasoftware.Opera", "Default", "History"),
            ]},
            "safari":  {"name": "Safari",  "type": "safari",   "paths": [
                os.path.join(home, "Library", "Safari", "History.db"),
            ]},
            "firefox": {"name": "Firefox", "type": "firefox",  "paths": _find_firefox_db()},
        }

    elif SYSTEM == "Windows":
        catalog = {
            "arc":     {"name": "Arc",     "type": "chromium", "paths": _arc_windows_paths()},
            "chrome":  {"name": "Chrome",  "type": "chromium", "paths": [
                os.path.join(local, "Google", "Chrome", "User Data", "Default", "History"),
            ]},
            "brave":   {"name": "Brave",   "type": "chromium", "paths": [
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History"),
            ]},
            "edge":    {"name": "Edge",    "type": "chromium", "paths": [
                os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "History"),
            ]},
            "vivaldi": {"name": "Vivaldi", "type": "chromium", "paths": [
                os.path.join(local, "Vivaldi", "User Data", "Default", "History"),
            ]},
            "opera":   {"name": "Opera",   "type": "chromium", "paths": [
                os.path.join(roaming, "Opera Software", "Opera Stable", "History"),
            ]},
            "firefox": {"name": "Firefox", "type": "firefox",  "paths": _find_firefox_db()},
        }

    else:  # Linux
        config = os.path.join(home, ".config")
        catalog = {
            "chrome":  {"name": "Chrome",  "type": "chromium", "paths": [
                os.path.join(config, "google-chrome", "Default", "History"),
            ]},
            "brave":   {"name": "Brave",   "type": "chromium", "paths": [
                os.path.join(config, "BraveSoftware", "Brave-Browser", "Default", "History"),
            ]},
            "edge":    {"name": "Edge",    "type": "chromium", "paths": [
                os.path.join(config, "microsoft-edge", "Default", "History"),
            ]},
            "vivaldi": {"name": "Vivaldi", "type": "chromium", "paths": [
                os.path.join(config, "vivaldi", "Default", "History"),
            ]},
            "opera":   {"name": "Opera",   "type": "chromium", "paths": [
                os.path.join(config, "opera", "History"),
            ]},
            "firefox": {"name": "Firefox", "type": "firefox",  "paths": _find_firefox_db()},
        }

    return catalog


def find_available_browsers():
    catalog = build_browser_catalog()
    available = []
    for key, info in catalog.items():
        for path in info["paths"]:
            if os.path.isfile(path):
                available.append((key, info["name"], info["type"], path))
                break
    return available


# --------------------------------------------------------------------------- #
# DB 읽기
# --------------------------------------------------------------------------- #

def _copy_and_connect(db_path):
    """브라우저가 열려 있어도 읽을 수 있도록 임시 복사 후 연결."""
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(db_path, tmp)
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    return conn, tmp


def read_chromium_history(db_path, days=None):
    tmp = None
    try:
        conn, tmp = _copy_and_connect(db_path)
        c = conn.cursor()
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = int((cutoff - CHROMIUM_EPOCH).total_seconds() * 1_000_000)
            c.execute("""
                SELECT u.url, u.title, u.visit_count,
                       v.visit_time, v.visit_duration
                FROM visits v JOIN urls u ON v.url = u.id
                WHERE v.visit_time > ?
                ORDER BY v.visit_time DESC
            """, (cutoff_ts,))
        else:
            c.execute("""
                SELECT u.url, u.title, u.visit_count,
                       v.visit_time, v.visit_duration
                FROM visits v JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
            """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except PermissionError:
        console.print("[yellow]  접근 권한 없음 — 브라우저가 열려 있다면 닫아보세요.[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]  DB 읽기 오류: {e}[/red]")
        return []
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def read_firefox_history(db_path, days=None):
    tmp = None
    try:
        conn, tmp = _copy_and_connect(db_path)
        c = conn.cursor()
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = int((cutoff - UNIX_EPOCH).total_seconds() * 1_000_000)
            c.execute("""
                SELECT p.url, p.title, p.visit_count,
                       v.visit_date
                FROM moz_historyvisits v JOIN moz_places p ON v.place_id = p.id
                WHERE v.visit_date > ?
                ORDER BY v.visit_date DESC
            """, (cutoff_ts,))
        else:
            c.execute("""
                SELECT p.url, p.title, p.visit_count,
                       v.visit_date
                FROM moz_historyvisits v JOIN moz_places p ON v.place_id = p.id
                ORDER BY v.visit_date DESC
            """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except PermissionError:
        console.print("[yellow]  Firefox: 접근 권한 없음.[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]  Firefox DB 읽기 오류: {e}[/red]")
        return []
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def read_safari_history(db_path, days=None):
    tmp = None
    try:
        conn, tmp = _copy_and_connect(db_path)
        c = conn.cursor()
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = (cutoff - SAFARI_EPOCH).total_seconds()
            c.execute("""
                SELECT hi.url, hv.title, hv.visit_time
                FROM history_visits hv JOIN history_items hi ON hv.history_item = hi.id
                WHERE hv.visit_time > ?
                ORDER BY hv.visit_time DESC
            """, (cutoff_ts,))
        else:
            c.execute("""
                SELECT hi.url, hv.title, hv.visit_time
                FROM history_visits hv JOIN history_items hi ON hv.history_item = hi.id
                ORDER BY hv.visit_time DESC
            """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except PermissionError:
        console.print(
            "[yellow]  Safari: 접근 권한 없음.\n"
            "  시스템 설정 > 개인 정보 보호 > 전체 디스크 접근에서 터미널을 추가하세요.[/yellow]"
        )
        return []
    except Exception as e:
        console.print(f"[red]  Safari DB 읽기 오류: {e}[/red]")
        return []
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def load_history(browser_key, db_type, db_path, days=None):
    if db_type == "firefox":
        raw = read_firefox_history(db_path, days)
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "visit_time": unix_ts_to_dt(r.get("visit_date")),
                "visit_duration": 0,
                "visit_count": r.get("visit_count", 1),
            }
            for r in raw
        ]
    elif db_type == "safari":
        raw = read_safari_history(db_path, days)
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "visit_time": safari_ts_to_dt(r.get("visit_time")),
                "visit_duration": 0,
                "visit_count": 1,
            }
            for r in raw
        ]
    else:  # chromium
        raw = read_chromium_history(db_path, days)
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "visit_time": chromium_ts_to_dt(r.get("visit_time")),
                "visit_duration": r.get("visit_duration", 0),
                "visit_count": r.get("visit_count", 1),
            }
            for r in raw
        ]


# --------------------------------------------------------------------------- #
# 분석
# --------------------------------------------------------------------------- #

def get_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or url[:50]
    except Exception:
        return url[:50]


def is_internal(url):
    return not url or any(url.startswith(p) for p in INTERNAL_PREFIXES)


def analyze_visits(visits):
    domain_stats = defaultdict(lambda: {
        "count": 0, "total_duration": 0, "last_visit": None,
    })
    hourly_counts = defaultdict(int)
    daily_counts = defaultdict(int)
    weekday_counts = defaultdict(int)

    for v in visits:
        url = v.get("url", "")
        if is_internal(url):
            continue
        domain = get_domain(url)
        if not domain:
            continue

        domain_stats[domain]["count"] += 1
        domain_stats[domain]["total_duration"] += v.get("visit_duration", 0) or 0

        dt = v.get("visit_time")
        if dt:
            lv = domain_stats[domain]["last_visit"]
            if lv is None or dt > lv:
                domain_stats[domain]["last_visit"] = dt
            hourly_counts[dt.hour] += 1
            daily_counts[dt.strftime("%Y-%m-%d")] += 1
            weekday_counts[dt.weekday()] += 1

    return domain_stats, hourly_counts, daily_counts, weekday_counts


# --------------------------------------------------------------------------- #
# 출력
# --------------------------------------------------------------------------- #

def show_top_sites(domain_stats, limit=20, sort_by="count"):
    key_fn = (lambda x: x[1]["total_duration"]) if sort_by == "duration" else (lambda x: x[1]["count"])
    sorted_domains = sorted(domain_stats.items(), key=key_fn, reverse=True)[:limit]

    table = Table(
        title=f"자주 방문한 웹사이트 Top {limit}",
        box=box.ROUNDED, header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("도메인", style="bold white", min_width=25)
    table.add_column("방문 수", justify="right", style="green")
    table.add_column("총 체류 시간", justify="right", style="yellow")
    table.add_column("마지막 방문", justify="right", style="blue")

    for i, (domain, stats) in enumerate(sorted_domains, 1):
        last = stats["last_visit"]
        table.add_row(
            str(i), domain,
            f"{stats['count']:,}",
            duration_to_str(stats["total_duration"]),
            last.strftime("%m/%d %H:%M") if last else "-",
        )
    console.print(table)


def show_hourly_heatmap(hourly_counts):
    if not hourly_counts:
        return
    max_count = max(hourly_counts.values())
    blocks = ["░", "▒", "▓", "█"]

    console.print("\n[bold cyan]시간대별 방문 패턴[/bold cyan]")
    console.print("[dim]0시                    12시                   23시[/dim]")
    bar = ""
    for hour in range(24):
        count = hourly_counts.get(hour, 0)
        ratio = count / max_count if max_count else 0
        block = blocks[int(ratio * (len(blocks) - 1))]
        if ratio == 0:
            bar += f"[dim]{block}[/dim]"
        elif ratio < 0.33:
            bar += f"[blue]{block}[/blue]"
        elif ratio < 0.66:
            bar += f"[yellow]{block}[/yellow]"
        else:
            bar += f"[red]{block}[/red]"
    console.print(bar)

    peaks = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_str = ", ".join(f"[bold]{h}시[/bold]({c:,}회)" for h, c in peaks)
    console.print(f"  피크 시간대: {peak_str}")


def show_weekday_chart(weekday_counts):
    if not weekday_counts:
        return
    days_ko = ["월", "화", "수", "목", "금", "토", "일"]
    max_count = max(weekday_counts.values())
    console.print("\n[bold cyan]요일별 방문 패턴[/bold cyan]")
    for wd in range(7):
        count = weekday_counts.get(wd, 0)
        ratio = count / max_count if max_count else 0
        bar = "█" * int(ratio * 30)
        color = "magenta" if wd >= 5 else "green"
        console.print(f"  {days_ko[wd]} [{color}]{bar:<30}[/{color}] {count:,}")


def show_daily_trend(daily_counts, days=14):
    if not daily_counts:
        return
    sorted_days = sorted(daily_counts.items())[-days:]
    if not sorted_days:
        return
    max_count = max(c for _, c in sorted_days)
    console.print(f"\n[bold cyan]최근 {days}일 방문 추이[/bold cyan]")
    for date_str, count in sorted_days:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            label = dt.strftime("%m/%d")
            wd = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
            color = "magenta" if dt.weekday() >= 5 else "cyan"
        except Exception:
            label, wd, color = date_str[-5:], "", "cyan"
        bar = "█" * int((count / max_count if max_count else 0) * 25)
        console.print(f"  {label}({wd}) [{color}]{bar:<25}[/{color}] {count:,}")


def show_summary_stats(visits, browser_name, days=None):
    total = len(visits)
    total_duration = sum(v.get("visit_duration", 0) or 0 for v in visits)
    unique_domains = len(set(
        get_domain(v["url"]) for v in visits if not is_internal(v.get("url", ""))
    ))
    period = f"최근 {days}일" if days else "전체"

    stats_text = Text()
    stats_text.append("  총 방문 수:      ", style="dim")
    stats_text.append(f"{total:,}회\n", style="bold green")
    stats_text.append("  방문 도메인 수:  ", style="dim")
    stats_text.append(f"{unique_domains:,}개\n", style="bold cyan")
    stats_text.append("  총 체류 시간:    ", style="dim")
    stats_text.append(f"{duration_to_str(total_duration)}\n", style="bold yellow")

    times = [v["visit_time"] for v in visits if v.get("visit_time")]
    if times:
        stats_text.append("  분석 기간:       ", style="dim")
        stats_text.append(
            f"{min(times).strftime('%Y-%m-%d')} ~ {max(times).strftime('%Y-%m-%d')}",
            style="bold white",
        )

    console.print(Panel(
        stats_text,
        title=f"[bold magenta]{browser_name} 브라우저 통계 ({period})[/bold magenta]",
        border_style="magenta",
    ))


# --------------------------------------------------------------------------- #
# 명령 핸들러
# --------------------------------------------------------------------------- #

def cmd_stats(args):
    available = find_available_browsers()
    if not available:
        console.print("[red]설치된 브라우저를 찾을 수 없습니다.[/red]")
        return

    if args.browser:
        available = [(k, n, t, p) for k, n, t, p in available if k == args.browser.lower()]
        if not available:
            console.print(f"[red]브라우저 '{args.browser}'를 찾을 수 없습니다.[/red]")
            return

    days = args.days

    for browser_key, browser_name, db_type, db_path in available:
        console.print(f"\n[bold blue]>>> {browser_name} 분석 중...[/bold blue]")
        visits = load_history(browser_key, db_type, db_path, days)
        if not visits:
            console.print("[yellow]  방문 기록이 없습니다.[/yellow]")
            continue

        show_summary_stats(visits, browser_name, days)
        domain_stats, hourly_counts, daily_counts, weekday_counts = analyze_visits(visits)
        show_top_sites(domain_stats, limit=args.top, sort_by=args.sort)
        show_hourly_heatmap(hourly_counts)
        show_weekday_chart(weekday_counts)
        show_daily_trend(daily_counts, days=min(14, days or 14))


def cmd_top(args):
    available = find_available_browsers()
    if not available:
        console.print("[red]설치된 브라우저를 찾을 수 없습니다.[/red]")
        return

    if args.browser:
        available = [(k, n, t, p) for k, n, t, p in available if k == args.browser.lower()]

    all_visits = []
    for browser_key, browser_name, db_type, db_path in available:
        all_visits.extend(load_history(browser_key, db_type, db_path, args.days))

    if not all_visits:
        console.print("[yellow]방문 기록이 없습니다.[/yellow]")
        return

    period = f"최근 {args.days}일" if args.days else "전체"
    label = args.browser or "전체 브라우저"
    console.print(f"\n[bold magenta]{label} | {period}[/bold magenta]")
    domain_stats, _, _, _ = analyze_visits(all_visits)
    show_top_sites(domain_stats, limit=args.limit, sort_by=args.sort)


def cmd_list_browsers(args):
    available = find_available_browsers()
    if not available:
        console.print(f"[red]설치된 브라우저를 찾을 수 없습니다. (현재 OS: {SYSTEM})[/red]")
        return

    table = Table(title=f"감지된 브라우저 ({SYSTEM})", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("키", style="yellow")
    table.add_column("브라우저", style="bold white")
    table.add_column("타입", style="dim")
    table.add_column("DB 경로", style="dim")

    for key, name, db_type, path in available:
        table.add_row(key, name, db_type, path)

    console.print(table)
    console.print("\n사용법: [bold]browser-history stats --browser <키>[/bold]")


# --------------------------------------------------------------------------- #
# 진입점
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        prog="browser-history",
        description="브라우저 방문 기록 분석 CLI (macOS / Windows / Linux)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  browser-history stats                      # 전체 통계
  browser-history stats --days 7             # 최근 7일
  browser-history stats --browser chrome     # Chrome만
  browser-history top --sort duration        # 체류 시간순 Top 20
  browser-history top --limit 30 --days 30   # 최근 30일 Top 30
  browser-history browsers                   # 브라우저 목록
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    stats_p = subparsers.add_parser("stats", help="브라우저 방문 통계 분석")
    stats_p.add_argument("--browser", "-b",
                         help="특정 브라우저 (arc, chrome, brave, edge, vivaldi, opera, firefox, safari)")
    stats_p.add_argument("--days", "-d", type=int, default=None, help="최근 N일 (기본: 전체)")
    stats_p.add_argument("--top", "-t", type=int, default=20, help="상위 N개 사이트 (기본: 20)")
    stats_p.add_argument("--sort", "-s", choices=["count", "duration"], default="count",
                         help="정렬 기준: count(방문수) | duration(체류시간) (기본: count)")

    top_p = subparsers.add_parser("top", help="자주 방문한 사이트 순위")
    top_p.add_argument("--browser", "-b", help="특정 브라우저만")
    top_p.add_argument("--days", "-d", type=int, default=None, help="최근 N일 (기본: 전체)")
    top_p.add_argument("--limit", "-l", type=int, default=20, help="표시할 수 (기본: 20)")
    top_p.add_argument("--sort", "-s", choices=["count", "duration"], default="count",
                       help="정렬 기준 (기본: count)")

    subparsers.add_parser("browsers", help="감지된 브라우저 목록")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "top":
        cmd_top(args)
    elif args.command == "browsers":
        cmd_list_browsers(args)
    else:
        args.browser = None
        args.days = None
        args.top = 20
        args.sort = "count"
        cmd_stats(args)


if __name__ == "__main__":
    main()
