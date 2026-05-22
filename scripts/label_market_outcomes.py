#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTCOME_PATH = ROOT / "data" / "outcome_labels.csv"
REPORT_PATH = ROOT / "data" / "runs" / "market_label_audit.json"

MARKET_FIELDS = [
    "briefing_pdf_release_date",
    "briefing_pdf_release_date_source",
    "briefing_pdf_release_date_confidence",
    "market_ticker_used",
    "ticker_price_at_release",
    "benchmark_used",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_10d",
    "abn_return_1d",
    "abn_return_3d",
    "abn_return_5d",
    "abn_return_10d",
    "volume_ratio_3d",
    "market_label",
    "market_label_source",
    "market_label_notes",
]

USER_AGENT = "Mozilla/5.0 FDA-AdCom-Monitor/0.1"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_market_fields(fieldnames: list[str], rows: list[dict[str, str]]) -> list[str]:
    output = list(fieldnames)
    insert_after = "fda_decision_date"
    insert_at = output.index(insert_after) + 1 if insert_after in output else len(output)
    for field in MARKET_FIELDS:
        if field not in output:
            output.insert(insert_at, field)
            insert_at += 1
        for row in rows:
            row.setdefault(field, "")
    return output


def parse_date(date_text: str) -> datetime:
    return datetime.fromisoformat(date_text)


def fetch_yahoo_daily(ticker: str, start_date: str, days_after: int = 20) -> list[dict]:
    start = parse_date(start_date)
    end = start + timedelta(days=days_after + 10)
    params = {
        "period1": int((start - timedelta(days=10)).timestamp()),
        "period2": int(end.timestamp()),
        "interval": "1d",
        "events": "history",
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{urlencode(params)}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    rows = []
    for stamp, close, volume in zip(timestamps, closes, volumes):
        if close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(stamp).date().isoformat(),
                "close": float(close),
                "volume": int(volume or 0),
            }
        )
    return rows


def first_index_on_or_after(rows: list[dict], date_text: str) -> int | None:
    target = parse_date(date_text).date().isoformat()
    for index, row in enumerate(rows):
        if row["date"] >= target:
            return index
    return None


def pct_return(start: float, end: float) -> float:
    return round((end / start - 1) * 100, 4)


def market_label(abnormal_return_3d: float | None) -> str:
    if abnormal_return_3d is None:
        return ""
    if abnormal_return_3d <= -10:
        return "STRONG_DOWN"
    if abnormal_return_3d <= -3:
        return "DOWN"
    if abnormal_return_3d >= 10:
        return "STRONG_UP"
    if abnormal_return_3d >= 3:
        return "UP"
    return "NEUTRAL"


def volume_ratio(rows: list[dict], start_index: int) -> float | None:
    prior = [row["volume"] for row in rows[max(0, start_index - 20) : start_index] if row["volume"]]
    after = [row["volume"] for row in rows[start_index : start_index + 3] if row["volume"]]
    if not prior or not after:
        return None
    return round((sum(after) / len(after)) / (sum(prior) / len(prior)), 4)


def apply_market_label(row: dict[str, str], benchmark: str) -> tuple[dict[str, str], str]:
    ticker = normalize_market_ticker(clean(row.get("ticker")))
    release_date = clean(row.get("briefing_pdf_release_date"))
    if not ticker:
        row["market_label_notes"] = merge_note(row.get("market_label_notes", ""), "MARKET_TODO_TICKER")
        return row, "missing_ticker"
    if not release_date:
        row["market_label_notes"] = merge_note(
            row.get("market_label_notes", ""), "MARKET_TODO_RELEASE_DATE"
        )
        return row, "missing_release_date"
    row["market_label_notes"] = remove_notes(
        row.get("market_label_notes", ""),
        ["MARKET_TODO_RELEASE_DATE", "MARKET_TODO_TICKER"],
    )

    ticker_rows = fetch_yahoo_daily(ticker, release_date)
    benchmark_rows = fetch_yahoo_daily(benchmark, release_date)
    ticker_index = first_index_on_or_after(ticker_rows, release_date)
    benchmark_index = first_index_on_or_after(benchmark_rows, release_date)
    if ticker_index is None or benchmark_index is None:
        row["market_label_notes"] = merge_note(row.get("market_label_notes", ""), "MARKET_NO_PRICE")
        return row, "missing_price"

    base = ticker_rows[ticker_index]["close"]
    benchmark_base = benchmark_rows[benchmark_index]["close"]
    row["ticker_price_at_release"] = f"{base:.4f}"
    row["market_ticker_used"] = ticker
    row["benchmark_used"] = benchmark
    row["market_label_source"] = "Yahoo Finance chart API"

    abnormal_3d = None
    for horizon in [1, 3, 5, 10]:
        ticker_end_index = min(ticker_index + horizon, len(ticker_rows) - 1)
        benchmark_end_index = min(benchmark_index + horizon, len(benchmark_rows) - 1)
        raw_return = pct_return(base, ticker_rows[ticker_end_index]["close"])
        benchmark_return = pct_return(benchmark_base, benchmark_rows[benchmark_end_index]["close"])
        abnormal_return = round(raw_return - benchmark_return, 4)
        row[f"return_{horizon}d"] = f"{raw_return:.4f}"
        row[f"abn_return_{horizon}d"] = f"{abnormal_return:.4f}"
        if horizon == 3:
            abnormal_3d = abnormal_return

    ratio = volume_ratio(ticker_rows, ticker_index)
    if ratio is not None:
        row["volume_ratio_3d"] = f"{ratio:.4f}"
    row["market_label"] = market_label(abnormal_3d)
    row["market_label_notes"] = merge_note(
        remove_prefixed_notes(row.get("market_label_notes", ""), "MARKET_ERROR:"),
        "MARKET_LABEL_COMPUTED",
    )
    return row, "computed"


def normalize_market_ticker(ticker: str) -> str:
    ticker = ticker.strip()
    if "/" in ticker:
        ticker = ticker.split("/", 1)[0]
    if "," in ticker:
        ticker = ticker.split(",", 1)[0]
    if ";" in ticker:
        ticker = ticker.split(";", 1)[0]
    return ticker.strip()


def merge_note(existing: str, note: str) -> str:
    parts = [part.strip() for part in clean(existing).split(";") if part.strip()]
    if note not in parts:
        parts.append(note)
    return "; ".join(parts)


def remove_notes(existing: str, notes: list[str]) -> str:
    parts = [part.strip() for part in clean(existing).split(";") if part.strip()]
    return "; ".join(part for part in parts if part not in notes)


def remove_prefixed_notes(existing: str, prefix: str) -> str:
    parts = [part.strip() for part in clean(existing).split(";") if part.strip()]
    return "; ".join(part for part in parts if not part.startswith(prefix))


def build_report(rows: list[dict[str, str]], statuses: list[str]) -> dict:
    return {
        "total_rows": len(rows),
        "rows_with_ticker": sum(1 for row in rows if clean(row.get("ticker"))),
        "rows_with_briefing_pdf_release_date": sum(
            1 for row in rows if clean(row.get("briefing_pdf_release_date"))
        ),
        "rows_with_market_label": sum(1 for row in rows if clean(row.get("market_label"))),
        "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "missing_release_date": [
            {
                "document_id": row.get("document_id", ""),
                "ticker": row.get("ticker", ""),
                "drug": row.get("drug", ""),
                "meeting_date": row.get("meeting_date", ""),
            }
            for row in rows
            if clean(row.get("ticker")) and not clean(row.get("briefing_pdf_release_date"))
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="IBB")
    parser.add_argument("--update", action="store_true", help="Write market fields back to outcome CSV")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    fieldnames, rows = read_rows(OUTCOME_PATH)
    fieldnames = ensure_market_fields(fieldnames, rows)
    statuses = []
    for row in rows:
        if clean(row.get("market_label")) and not args.update:
            statuses.append("already_labeled")
            continue
        try:
            _row, status = apply_market_label(row, args.benchmark)
        except Exception as exc:  # noqa: BLE001
            row["market_label_notes"] = merge_note(row.get("market_label_notes", ""), f"MARKET_ERROR: {exc}")
            status = "error"
        statuses.append(status)

    report = build_report(rows, statuses)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.update:
        write_rows(OUTCOME_PATH, fieldnames, rows)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
