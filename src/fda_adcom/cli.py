from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fda_adcom.config import Settings
from fda_adcom.fda_monitor import candidate_to_dict, discover_documents, discover_event_pages
from fda_adcom.history import enrich_market_for_ranked, map_history_tickers, rank_history
from fda_adcom.history import initialize_outcome_labels, mini_backtest
from fda_adcom.pipeline import (
    analyze_ranked_history,
    backfill_history,
    bootstrap_seen,
    process_pdf,
    run_once,
    watch,
)


def infer_meeting_date(title: str) -> str | None:
    match = re.search(
        r"\b("
        r"January|February|March|April|May|June|July|August|September|October|November|December"
        r")\s+\d{1,2}(?:-\d{1,2})?,\s+\d{4}\b",
        title,
    )
    if not match:
        return None
    date_text = match.group(0)
    date_text = re.sub(r"(\d{1,2})-\d{1,2}", r"\1", date_text)
    try:
        return datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def build_event_summary(path: Path, payload: dict) -> dict:
    title = payload.get("document", {}).get("title") or ""
    meeting_date = infer_meeting_date(title)
    stale_historical = False
    if meeting_date:
        meeting_day = datetime.fromisoformat(meeting_date).date()
        stale_historical = meeting_day < (datetime.now(timezone.utc).date() - timedelta(days=30))
    return {
        "file": str(path),
        "title": title,
        "meeting_date": meeting_date,
        "stale_historical": stale_historical,
        "signal": payload.get("signal", {}).get("label"),
        "probability": payload.get("signal", {}).get("probability"),
        "confidence": payload.get("signal", {}).get("confidence"),
        "source_page": payload.get("document", {}).get("source_page"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fda-adcom")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--dry-run", action="store_true")

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--pages", action="store_true", help="List crawled FDA pages instead of documents")
    discover_parser.add_argument("--max-pages", type=int, default=None)

    bootstrap_parser = subparsers.add_parser("bootstrap-seen")
    bootstrap_parser.add_argument("--max-pages", type=int, default=None)

    backfill_parser = subparsers.add_parser("backfill-history")
    backfill_parser.add_argument("--max-pages", type=int, default=None)
    backfill_parser.add_argument("--limit", type=int, default=5)
    backfill_parser.add_argument("--include-sponsor", action="store_true")
    backfill_parser.add_argument("--no-skip-existing", action="store_true")
    backfill_parser.add_argument("--analyze", action="store_true", help="Call the configured AI model")

    rank_parser = subparsers.add_parser("rank-history")
    rank_parser.add_argument("--limit", type=int, default=25)
    rank_parser.add_argument("--output", default="")

    analyze_ranked_parser = subparsers.add_parser("analyze-ranked-history")
    analyze_ranked_parser.add_argument("--limit", type=int, default=1)
    analyze_ranked_parser.add_argument("--min-score", type=int, default=70)

    market_parser = subparsers.add_parser("enrich-market")
    market_parser.add_argument("--limit", type=int, default=25)
    market_parser.add_argument("--output", default="")

    map_parser = subparsers.add_parser("map-tickers")
    map_parser.add_argument("--limit", type=int, default=50)
    map_parser.add_argument("--output", default="")

    outcomes_parser = subparsers.add_parser("init-outcomes")
    outcomes_parser.add_argument("--limit", type=int, default=50)

    backtest_parser = subparsers.add_parser("mini-backtest")
    backtest_parser.add_argument("--output", default="")

    report_parser = subparsers.add_parser("daily-report")
    report_parser.add_argument("--hours", type=int, default=24)

    subparsers.add_parser("watch")

    analyze_parser = subparsers.add_parser("analyze-pdf")
    analyze_parser.add_argument("pdf_path")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()

    if args.command == "run-once":
        results = run_once(settings, dry_run=args.dry_run)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.command == "discover":
        max_pages = args.max_pages or settings.crawl_max_pages
        if args.pages:
            pages = discover_event_pages(
                settings.calendar_url,
                settings.recent_url,
                seed_urls=settings.seed_urls,
                max_pages=max_pages,
            )
            print(json.dumps(pages, indent=2, ensure_ascii=False))
            return
        documents = discover_documents(
            settings.calendar_url,
            settings.recent_url,
            seed_urls=settings.seed_urls,
            max_pages=max_pages,
        )
        print(json.dumps([candidate_to_dict(document) for document in documents], indent=2, ensure_ascii=False))
        return

    if args.command == "bootstrap-seen":
        marked = bootstrap_seen(settings, max_pages=args.max_pages)
        print(json.dumps(marked, indent=2, ensure_ascii=False))
        return

    if args.command == "backfill-history":
        results = backfill_history(
            settings,
            max_pages=args.max_pages,
            limit=args.limit,
            fda_only=not args.include_sponsor,
            skip_existing=not args.no_skip_existing,
            analyze=args.analyze,
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.command == "rank-history":
        ranked = rank_history(
            settings.data_dir / "history_runs",
            settings.data_dir / "sponsor_tickers.csv",
            limit=args.limit,
        )
        if args.output:
            Path(args.output).write_text(json.dumps(ranked, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(ranked, indent=2, ensure_ascii=False))
        return

    if args.command == "analyze-ranked-history":
        results = analyze_ranked_history(settings, limit=args.limit, min_score=args.min_score)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.command == "enrich-market":
        ranked = rank_history(
            settings.data_dir / "history_runs",
            settings.data_dir / "sponsor_tickers.csv",
            limit=args.limit,
        )
        enriched = enrich_market_for_ranked(ranked)
        if args.output:
            Path(args.output).write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(enriched, indent=2, ensure_ascii=False))
        return

    if args.command == "map-tickers":
        mapped = map_history_tickers(
            settings.data_dir / "history_runs",
            settings.data_dir / "sponsor_tickers.csv",
            limit=args.limit,
        )
        if args.output:
            Path(args.output).write_text(json.dumps(mapped, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(mapped, indent=2, ensure_ascii=False))
        return

    if args.command == "init-outcomes":
        rows = initialize_outcome_labels(
            settings.data_dir / "history_runs",
            settings.data_dir / "sponsor_tickers.csv",
            settings.data_dir / "outcome_labels.csv",
            limit=args.limit,
        )
        print(json.dumps({"rows": len(rows), "path": str(settings.data_dir / "outcome_labels.csv")}, indent=2))
        return

    if args.command == "mini-backtest":
        result = mini_backtest(
            settings.data_dir / "history_runs",
            settings.data_dir / "sponsor_tickers.csv",
            settings.data_dir / "outcome_labels.csv",
        )
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "daily-report":
        settings.ensure_dirs()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
        run_files = [
            path
            for path in (settings.data_dir / "runs").glob("*.json")
            if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) >= cutoff
        ]
        event_files = []
        for path in sorted(run_files, key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "signal" in payload and "document" in payload:
                event_files.append((path, payload))

        watch_pid_path = settings.data_dir / "watch.pid"
        watch_status = "unknown"
        if watch_pid_path.exists():
            pid = watch_pid_path.read_text(encoding="utf-8").strip()
            if pid:
                try:
                    os.kill(int(pid), 0)
                    watch_status = "running"
                except OSError:
                    watch_status = "not running"

        paper_path = settings.data_dir / "paper_trades.csv"
        paper_rows = 0
        if paper_path.exists():
            paper_rows = max(0, len(paper_path.read_text(encoding="utf-8").splitlines()) - 1)

        summary = {
            "watch_status": watch_status,
            "hours_checked": args.hours,
            "new_signal_files": len(event_files),
            "paper_trade_rows": paper_rows,
            "events": [
                build_event_summary(path, payload)
                for path, payload in event_files[:20]
            ],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    if args.command == "watch":
        watch(settings)
        return

    if args.command == "analyze-pdf":
        settings.ensure_dirs()
        result = process_pdf(settings, Path(args.pdf_path))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    raise SystemExit(f"Unknown command: {args.command}")
