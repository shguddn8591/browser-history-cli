#!/usr/bin/env python3
"""
브라우저 방문 기록 분석 CLI
지원 브라우저: Arc, Chrome, Brave, Edge, Vivaldi, Opera, Safari
"""

import argparse
import sqlite3
import shutil
import tempfile
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    from rich.progress import track
    from rich import box
    import rich.style
except ImportError:
    print("rich 라이브러리가 필요합니다: pip3 install rich")
    sys.exit(1)

console = Console()

# Chromium epoch: 1601-01-01 기준 microseconds
CHROMIUM_EPOCH = datetime(1601, 1, 1)

def chromium_time_to_datetime(microseconds):
    if not microseconds:
        return None
    try:
        return CHROMIUM_EPOCH + timedelta(microseconds=microseconds)
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

BROWSERS = {
    "arc": {
        "name": "Arc",
        "paths": [
            os.path.expanduser("~/Library/Application Support/Arc/User Data/Default/History"),
        ],
    },
    "chrome": {
        "name": "Chrome",
        "paths": [
            os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/History"),
        ],
    },
    "brave": {
        "name": "Brave",
        "paths": [
            os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History"),
        ],
    },
    "edge": {
        "name": "Edge",
        "paths": [
            os.path.expanduser("~/Library/Application Support/Microsoft Edge/Default/History"),
        ],
    },
    "vivaldi": {
        "name": "Vivaldi",
        "paths": [
            os.path.expanduser("~/Library/Application Support/Vivaldi/Default/History"),
        ],
    },
    "opera": {
        "name": "Opera",
        "paths": [
            os.path.expanduser("~/Library/Application Support/com.operasoftware.Opera/Default/History"),
        ],
    },
    "safari": {
        "name": "Safari",
        "paths": [
            os.path.expanduser("~/Library/Safari/History.db"),
        ],
    },
}

def find_available_browsers():
    available = []
    for key, info in BROWSERS.items():
        for path in info["paths"]:
            if os.path.exists(path):
                available.append((key, info["name"], path))
                break
    return available


def read_chromium_history(db_path, days=None):
    """Chromium 계열 브라우저 히스토리 읽기 (Arc, Chrome, Brave, Edge, Vivaldi, Opera)"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        shutil.copy2(db_path, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_chromium = int((cutoff - CHROMIUM_EPOCH).total_seconds() * 1_000_000)
            c.execute("""
                SELECT
                    u.url, u.title, u.visit_count,
                    v.visit_time, v.visit_duration
                FROM visits v
                JOIN urls u ON v.url = u.id
                WHERE v.visit_time > ?
                ORDER BY v.visit_time DESC
            """, (cutoff_chromium,))
        else:
            c.execute("""
                SELECT
                    u.url, u.title, u.visit_count,
                    v.visit_time, v.visit_duration
                FROM visits v
                JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
            """)

        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        console.print(f"[red]DB 읽기 오류: {e}[/red]")
        return []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_safari_history(db_path, days=None):
    """Safari 히스토리 읽기"""
    tmp = tempfile.mktemp(suffix=".db")
    try:
        shutil.copy2(db_path, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Safari uses Unix timestamp (seconds since 2001-01-01 = CoreData epoch)
        SAFARI_EPOCH = datetime(2001, 1, 1)

        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_safari = (cutoff - SAFARI_EPOCH).total_seconds()
            c.execute("""
                SELECT
                    hi.url, hv.title,
                    hv.visit_time
                FROM history_visits hv
                JOIN history_items hi ON hv.history_item = hi.id
                WHERE hv.visit_time > ?
                ORDER BY hv.visit_time DESC
            """, (cutoff_safari,))
        else:
            c.execute("""
                SELECT
                    hi.url, hv.title,
                    hv.visit_time
                FROM history_visits hv
                JOIN history_items hi ON hv.history_item = hi.id
                ORDER BY hv.visit_time DESC
            """)

        rows = c.fetchall()
        conn.close()

        SAFARI_EPOCH_DT = datetime(2001, 1, 1)
        result = []
        for r in rows:
            row = dict(r)
            if row.get("visit_time"):
                dt = SAFARI_EPOCH_DT + timedelta(seconds=row["visit_time"])
                row["_datetime"] = dt
                row["visit_duration"] = 0
                row["visit_count"] = 1
            result.append(row)
        return result
    except PermissionError:
        console.print("[yellow]  Safari: 접근 권한 없음. 시스템 환경설정 > 개인 정보 보호 > 전체 디스크 접근에서 터미널 권한을 부여하세요.[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]Safari DB 읽기 오류: {e}[/red]")
        return []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_history(browser_key, db_path, days=None):
    if browser_key == "safari":
        raw = read_safari_history(db_path, days)
        visits = []
        for r in raw:
            visits.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "visit_time": r.get("_datetime"),
                "visit_duration": 0,
                "visit_count": 1,
            })
    else:
        raw = read_chromium_history(db_path, days)
        visits = []
        for r in raw:
            dt = chromium_time_to_datetime(r.get("visit_time"))
            visits.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "visit_time": dt,
                "visit_duration": r.get("visit_duration", 0),
                "visit_count": r.get("visit_count", 1),
            })
    return visits


def get_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # www. 제거
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or url[:50]
    except Exception:
        return url[:50]


def analyze_visits(visits):
    """방문 데이터 분석"""
    domain_stats = defaultdict(lambda: {
        "count": 0,
        "total_duration": 0,
        "titles": set(),
        "last_visit": None,
    })
    hourly_counts = defaultdict(int)
    daily_counts = defaultdict(int)
    weekday_counts = defaultdict(int)

    for v in visits:
        url = v.get("url", "")
        if not url or url.startswith("chrome://") or url.startswith("arc://"):
            continue

        domain = get_domain(url)
        if not domain:
            continue

        domain_stats[domain]["count"] += 1
        domain_stats[domain]["total_duration"] += v.get("visit_duration", 0) or 0

        title = v.get("title", "")
        if title:
            domain_stats[domain]["titles"].add(title)

        dt = v.get("visit_time")
        if dt:
            if (domain_stats[domain]["last_visit"] is None or
                    dt > domain_stats[domain]["last_visit"]):
                domain_stats[domain]["last_visit"] = dt

            hourly_counts[dt.hour] += 1
            daily_counts[dt.strftime("%Y-%m-%d")] += 1
            weekday_counts[dt.weekday()] += 1

    return domain_stats, hourly_counts, daily_counts, weekday_counts


def show_top_sites(domain_stats, limit=20, sort_by="count"):
    if sort_by == "duration":
        sorted_domains = sorted(
            domain_stats.items(),
            key=lambda x: x[1]["total_duration"],
            reverse=True
        )[:limit]
    else:
        sorted_domains = sorted(
            domain_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:limit]

    table = Table(
        title=f"자주 방문한 웹사이트 Top {limit}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("도메인", style="bold white", min_width=25)
    table.add_column("방문 수", justify="right", style="green")
    table.add_column("총 체류 시간", justify="right", style="yellow")
    table.add_column("마지막 방문", justify="right", style="blue")

    for i, (domain, stats) in enumerate(sorted_domains, 1):
        last = stats["last_visit"]
        last_str = last.strftime("%m/%d %H:%M") if last else "-"
        table.add_row(
            str(i),
            domain,
            f"{stats['count']:,}",
            duration_to_str(stats["total_duration"]),
            last_str,
        )

    console.print(table)


def show_hourly_heatmap(hourly_counts):
    if not hourly_counts:
        return

    max_count = max(hourly_counts.values()) if hourly_counts else 1
    blocks = ["░", "▒", "▓", "█"]

    console.print("\n[bold cyan]시간대별 방문 패턴[/bold cyan]")
    console.print("[dim]0시                    12시                   23시[/dim]")

    bar = ""
    for hour in range(24):
        count = hourly_counts.get(hour, 0)
        ratio = count / max_count if max_count > 0 else 0
        idx = int(ratio * (len(blocks) - 1))
        block = blocks[idx]
        if ratio == 0:
            bar += f"[dim]{block}[/dim]"
        elif ratio < 0.33:
            bar += f"[blue]{block}[/blue]"
        elif ratio < 0.66:
            bar += f"[yellow]{block}[/yellow]"
        else:
            bar += f"[red]{block}[/red]"
    console.print(bar)

    # 피크 시간
    peak_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_str = ", ".join([f"[bold]{h}시[/bold]({c:,}회)" for h, c in peak_hours])
    console.print(f"  피크 시간대: {peak_str}")


def show_weekday_chart(weekday_counts):
    if not weekday_counts:
        return

    days_ko = ["월", "화", "수", "목", "금", "토", "일"]
    max_count = max(weekday_counts.values()) if weekday_counts else 1

    console.print("\n[bold cyan]요일별 방문 패턴[/bold cyan]")
    for wd in range(7):
        count = weekday_counts.get(wd, 0)
        ratio = count / max_count if max_count > 0 else 0
        bar_len = int(ratio * 30)
        day_name = days_ko[wd]
        is_weekend = wd >= 5
        color = "magenta" if is_weekend else "green"
        bar = "█" * bar_len
        console.print(f"  {day_name} [{color}]{bar:<30}[/{color}] {count:,}")


def show_daily_trend(daily_counts, days=14):
    if not daily_counts:
        return

    sorted_days = sorted(daily_counts.items())[-days:]
    if not sorted_days:
        return

    max_count = max(c for _, c in sorted_days) if sorted_days else 1

    console.print(f"\n[bold cyan]최근 {days}일 방문 추이[/bold cyan]")
    for date_str, count in sorted_days:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            label = dt.strftime("%m/%d")
            wd = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
        except Exception:
            label = date_str[-5:]
            wd = ""
        ratio = count / max_count if max_count > 0 else 0
        bar_len = int(ratio * 25)
        is_weekend = dt.weekday() >= 5
        color = "magenta" if is_weekend else "cyan"
        bar = "█" * bar_len
        console.print(f"  {label}({wd}) [{color}]{bar:<25}[/{color}] {count:,}")


def show_summary_stats(visits, browser_name, days=None):
    total = len(visits)
    total_duration = sum(v.get("visit_duration", 0) or 0 for v in visits)
    unique_domains = len(set(
        get_domain(v["url"]) for v in visits
        if v.get("url") and not v["url"].startswith("chrome://")
    ))

    period = f"최근 {days}일" if days else "전체"
    title = f"{browser_name} 브라우저 통계 ({period})"

    stats_text = Text()
    stats_text.append(f"  총 방문 수:      ", style="dim")
    stats_text.append(f"{total:,}회\n", style="bold green")
    stats_text.append(f"  방문 도메인 수:  ", style="dim")
    stats_text.append(f"{unique_domains:,}개\n", style="bold cyan")
    stats_text.append(f"  총 체류 시간:    ", style="dim")
    stats_text.append(f"{duration_to_str(total_duration)}\n", style="bold yellow")

    if visits:
        times = [v["visit_time"] for v in visits if v.get("visit_time")]
        if times:
            earliest = min(times)
            latest = max(times)
            stats_text.append(f"  분석 기간:       ", style="dim")
            stats_text.append(f"{earliest.strftime('%Y-%m-%d')} ~ {latest.strftime('%Y-%m-%d')}", style="bold white")

    console.print(Panel(stats_text, title=f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))


def cmd_stats(args):
    available = find_available_browsers()
    if not available:
        console.print("[red]설치된 브라우저를 찾을 수 없습니다.[/red]")
        return

    # 브라우저 필터링
    if args.browser:
        available = [(k, n, p) for k, n, p in available if k == args.browser.lower()]
        if not available:
            console.print(f"[red]브라우저 '{args.browser}'를 찾을 수 없습니다.[/red]")
            return

    days = args.days if hasattr(args, "days") else None

    for browser_key, browser_name, db_path in available:
        console.print(f"\n[bold blue]>>> {browser_name} 분석 중...[/bold blue]")
        visits = load_history(browser_key, db_path, days)

        if not visits:
            console.print(f"[yellow]  방문 기록이 없습니다.[/yellow]")
            continue

        show_summary_stats(visits, browser_name, days)

        domain_stats, hourly_counts, daily_counts, weekday_counts = analyze_visits(visits)

        show_top_sites(domain_stats, limit=args.top, sort_by=args.sort)
        show_hourly_heatmap(hourly_counts)
        show_weekday_chart(weekday_counts)
        show_daily_trend(daily_counts, days=min(14, days or 14))


def cmd_list_browsers(args):
    available = find_available_browsers()
    if not available:
        console.print("[red]설치된 브라우저를 찾을 수 없습니다.[/red]")
        return

    table = Table(title="감지된 브라우저", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("키", style="yellow")
    table.add_column("브라우저", style="bold white")
    table.add_column("DB 경로", style="dim")

    for key, name, path in available:
        table.add_row(key, name, path)

    console.print(table)
    console.print("\n사용법: [bold]browser_history stats --browser <키>[/bold]")


def cmd_top(args):
    """도메인별 상세 분석"""
    available = find_available_browsers()
    if not available:
        console.print("[red]설치된 브라우저를 찾을 수 없습니다.[/red]")
        return

    if args.browser:
        available = [(k, n, p) for k, n, p in available if k == args.browser.lower()]

    days = args.days if hasattr(args, "days") else None
    all_visits = []

    for browser_key, browser_name, db_path in available:
        visits = load_history(browser_key, db_path, days)
        all_visits.extend(visits)

    if not all_visits:
        console.print("[yellow]방문 기록이 없습니다.[/yellow]")
        return

    domain_stats, _, _, _ = analyze_visits(all_visits)

    browser_label = args.browser or "전체 브라우저"
    period = f"최근 {days}일" if days else "전체"
    console.print(f"\n[bold magenta]{browser_label} | {period}[/bold magenta]")
    show_top_sites(domain_stats, limit=args.limit, sort_by=args.sort)


def main():
    parser = argparse.ArgumentParser(
        prog="browser_history",
        description="브라우저 방문 기록 분석 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python3 browser_history.py stats                    # 전체 통계
  python3 browser_history.py stats --days 7           # 최근 7일
  python3 browser_history.py stats --browser arc      # Arc만
  python3 browser_history.py top --limit 30 --days 30 # 최근 30일 Top 30
  python3 browser_history.py top --sort duration       # 체류 시간순 정렬
  python3 browser_history.py browsers                  # 브라우저 목록
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    # stats 명령
    stats_p = subparsers.add_parser("stats", help="브라우저 방문 통계 분석")
    stats_p.add_argument("--browser", "-b", help="특정 브라우저만 분석 (arc, chrome, brave, edge, vivaldi, opera, safari)")
    stats_p.add_argument("--days", "-d", type=int, default=None, help="최근 N일 분석 (기본: 전체)")
    stats_p.add_argument("--top", "-t", type=int, default=20, help="상위 N개 사이트 표시 (기본: 20)")
    stats_p.add_argument("--sort", "-s", choices=["count", "duration"], default="count",
                         help="정렬 기준: count(방문수) 또는 duration(체류시간) (기본: count)")

    # top 명령
    top_p = subparsers.add_parser("top", help="자주 방문한 사이트 순위")
    top_p.add_argument("--browser", "-b", help="특정 브라우저만 분석")
    top_p.add_argument("--days", "-d", type=int, default=None, help="최근 N일 (기본: 전체)")
    top_p.add_argument("--limit", "-l", type=int, default=20, help="표시할 사이트 수 (기본: 20)")
    top_p.add_argument("--sort", "-s", choices=["count", "duration"], default="count",
                       help="정렬 기준 (기본: count)")

    # browsers 명령
    subparsers.add_parser("browsers", help="감지된 브라우저 목록")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "top":
        cmd_top(args)
    elif args.command == "browsers":
        cmd_list_browsers(args)
    else:
        # 기본: stats 실행
        console.print("[bold cyan]브라우저 방문 기록 분석기[/bold cyan]\n")
        args.browser = None
        args.days = None
        args.top = 20
        args.sort = "count"
        cmd_stats(args)


if __name__ == "__main__":
    main()
