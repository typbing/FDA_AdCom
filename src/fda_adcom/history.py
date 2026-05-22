from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests


MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)

HIGH_VALUE_COMMITTEE_TERMS = [
    "oncologic drugs",
    "cardiovascular and renal drugs",
    "antimicrobial drugs",
    "endocrinologic and metabolic drugs",
    "peripheral and central nervous system drugs",
    "psychopharmacologic drugs",
    "arthritis",
    "dermatologic and ophthalmic drugs",
    "anesthetic and analgesic drug products",
    "nonprescription drugs",
    "obstetrics",
]


@dataclass(frozen=True)
class SponsorTicker:
    sponsor: str
    ticker: str


def infer_meeting_date(title: str) -> str | None:
    match = re.search(rf"\b({MONTH_PATTERN})\s+\d{{1,2}}(?:-\d{{1,2}})?,\s+\d{{4}}\b", title)
    if not match:
        return None
    date_text = re.sub(r"(\d{1,2})-\d{1,2}", r"\1", match.group(0))
    try:
        return datetime.strptime(date_text, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def load_ticker_map(path: Path) -> list[SponsorTicker]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            SponsorTicker(row["sponsor"].strip(), row["ticker"].strip())
            for row in rows
            if row.get("sponsor") and row.get("ticker")
        ]


def infer_sponsor(title: str, ticker_map: list[SponsorTicker]) -> str | None:
    lower = title.lower()
    for item in ticker_map:
        if item.sponsor.lower() in lower:
            return item.sponsor

    match = re.search(r"-\s+(.+?)\s+Briefing\s+(?:Document|Information|Materials)", title, re.I)
    if not match:
        return None
    sponsor = match.group(1)
    sponsor = re.sub(r"\([^)]*\)", "", sponsor)
    sponsor = re.sub(r"\b(FDA|Combined|Applicants?|and)\b", " ", sponsor, flags=re.I)
    sponsor = re.sub(r"\s+", " ", sponsor).strip(" -")
    return sponsor or None


def infer_ticker(title: str, ticker_map: list[SponsorTicker]) -> str | None:
    lower = title.lower()
    matches = [item for item in ticker_map if item.sponsor.lower() in lower]
    if matches:
        return sorted(matches, key=lambda item: len(item.sponsor), reverse=True)[0].ticker
    sponsor = infer_sponsor(title, ticker_map)
    if not sponsor:
        return None
    for item in ticker_map:
        if item.sponsor.lower() == sponsor.lower():
            return item.ticker
    return None


def load_history_records(history_dir: Path) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(history_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "document" in payload:
            records.append((path, payload))
    return records


def rank_history_record(path: Path, payload: dict, ticker_map: list[SponsorTicker]) -> dict:
    document = payload.get("document", {})
    title = document.get("title", "")
    source_page = document.get("source_page", "")
    title_lower = title.lower()
    lower = f"{title} {source_page}".lower()
    sections = set(payload.get("sections_found", []))
    page_count = int(payload.get("page_count") or 0)
    meeting_date = infer_meeting_date(title)
    sponsor = infer_sponsor(title, ticker_map)
    ticker = infer_ticker(title, ticker_map)
    reasons: list[str] = []

    score = 0

    document_quality = 0
    if "fda" in title_lower and ("briefing document" in title_lower or "briefing information" in title_lower):
        document_quality = 25
        reasons.append("FDA briefing document")
    elif "combined fda" in title_lower and "briefing" in title_lower:
        document_quality = 20
        reasons.append("combined FDA/applicant briefing")
    elif "background" in title_lower:
        document_quality = 18
        reasons.append("background material")
    elif "questions" in title_lower:
        document_quality = 10
        reasons.append("questions document")
    elif "briefing" in title_lower:
        document_quality = 8
        reasons.append("non-FDA briefing")
    score += document_quality

    if any(term in lower for term in HIGH_VALUE_COMMITTEE_TERMS):
        score += 15
        reasons.append("high-value human drug committee")
    elif "drugs advisory committee" in lower:
        score += 10
        reasons.append("human drug committee")

    if ticker:
        score += 20
        reasons.append(f"ticker mapped: {ticker}")
    elif sponsor:
        score += 8
        reasons.append(f"sponsor inferred: {sponsor}")

    if meeting_date and ticker:
        score += 20
        reasons.append("market reaction can be fetched")
    elif meeting_date:
        score += 8
        reasons.append("meeting date inferred")

    if "questions" in sections or "question" in lower:
        score += 15
        reasons.append("questions available")

    richness = 0
    if {"efficacy", "safety"}.issubset(sections):
        richness += 8
        reasons.append("efficacy and safety sections")
    if "questions" in sections:
        richness += 4
    if page_count >= 50:
        richness += 3
        reasons.append("substantial PDF length")
    score += min(15, richness)

    if payload.get("analysis") and payload.get("signal"):
        score += 5
        reasons.append("AI analysis already available")

    if "errata" in lower:
        score -= 25
        reasons.append("errata penalty")
    if "final questions" in lower and "briefing" not in lower:
        score -= 20
        reasons.append("questions-only penalty")
    if page_count and page_count < 10:
        score -= 15
        reasons.append("short document penalty")

    score = max(0, min(100, score))
    return {
        "file": str(path),
        "document_id": document.get("id"),
        "title": title,
        "url": document.get("url"),
        "source_page": source_page,
        "meeting_date": meeting_date,
        "sponsor": sponsor,
        "ticker": ticker,
        "page_count": page_count,
        "sections_found": sorted(sections),
        "has_ai_analysis": bool(payload.get("analysis") and payload.get("signal")),
        "value_score": score,
        "reasons": reasons,
    }


def source_page_ticker_index(records: list[tuple[Path, dict]], ticker_map: list[SponsorTicker]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for _path, payload in records:
        document = payload.get("document", {})
        title = document.get("title", "")
        source_page = document.get("source_page", "")
        ticker = infer_ticker(title, ticker_map)
        sponsor = infer_sponsor(title, ticker_map)
        if source_page and ticker:
            index[source_page] = {"ticker": ticker, "sponsor": sponsor}
    return index


def rank_history(history_dir: Path, ticker_map_path: Path, limit: int | None = None) -> list[dict]:
    ticker_map = load_ticker_map(ticker_map_path)
    records = load_history_records(history_dir)
    page_index = source_page_ticker_index(records, ticker_map)
    ranked = []
    for path, payload in records:
        if "error" in payload:
            continue
        item = rank_history_record(path, payload, ticker_map)
        page_mapping = page_index.get(item.get("source_page", ""))
        if page_mapping and not item.get("ticker"):
            item["ticker"] = page_mapping["ticker"]
            item["sponsor"] = page_mapping["sponsor"]
            item["value_score"] = min(100, item["value_score"] + 20)
            item["reasons"].append(f"ticker inferred from same meeting page: {item['ticker']}")
        ranked.append(item)
    ranked.sort(key=lambda item: (item["value_score"], item["page_count"]), reverse=True)
    return ranked[:limit] if limit else ranked


def map_history_tickers(history_dir: Path, ticker_map_path: Path, limit: int | None = None) -> list[dict]:
    ticker_map = load_ticker_map(ticker_map_path)
    records = load_history_records(history_dir)
    page_index = source_page_ticker_index(records, ticker_map)
    mapped = []
    for path, payload in records:
        document = payload.get("document", {})
        title = document.get("title", "")
        source_page = document.get("source_page", "")
        sponsor = infer_sponsor(title, ticker_map)
        ticker = infer_ticker(title, ticker_map)
        inferred_from_page = False
        if not ticker and source_page in page_index:
            sponsor = page_index[source_page].get("sponsor")
            ticker = page_index[source_page].get("ticker")
            inferred_from_page = True
        mapped.append(
            {
                "file": str(path),
                "document_id": document.get("id"),
                "title": title,
                "source_page": source_page,
                "meeting_date": infer_meeting_date(title),
                "sponsor": sponsor,
                "ticker": ticker,
                "inferred_from_page": inferred_from_page,
            }
        )
    mapped.sort(key=lambda item: (bool(item["ticker"]), item.get("meeting_date") or ""), reverse=True)
    return mapped[:limit] if limit else mapped


def fetch_yahoo_closes(ticker: str, start_date: str, days_after: int = 10) -> dict[str, float]:
    start = datetime.fromisoformat(start_date)
    end = start + timedelta(days=days_after + 7)
    period1 = int((start - timedelta(days=3)).timestamp())
    period2 = int(end.timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    response = requests.get(
        url,
        params={"period1": period1, "period2": period2, "interval": "1d", "events": "history"},
        headers={"User-Agent": "Mozilla/5.0 FDA-AdCom-Monitor/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    closes = quote.get("close") or []
    data: dict[str, float] = {}
    for stamp, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp).date().isoformat()
        data[day] = float(close)
    return data


def first_close_on_or_after(closes: dict[str, float], date_text: str) -> tuple[str, float] | None:
    start = datetime.fromisoformat(date_text).date()
    for offset in range(0, 10):
        day = (start + timedelta(days=offset)).isoformat()
        if day in closes:
            return day, closes[day]
    return None


def enrich_market_for_ranked(ranked: list[dict]) -> list[dict]:
    enriched = []
    cache: dict[tuple[str, str], dict[str, float]] = {}
    for item in ranked:
        ticker = item.get("ticker")
        meeting_date = item.get("meeting_date")
        if not ticker or not meeting_date:
            enriched.append(item | {"market_error": "missing ticker or meeting_date"})
            continue
        try:
            closes = cache.setdefault((ticker, meeting_date), fetch_yahoo_closes(ticker, meeting_date))
            entry = first_close_on_or_after(closes, meeting_date)
            day_1 = first_close_on_or_after(closes, (datetime.fromisoformat(meeting_date) + timedelta(days=1)).date().isoformat())
            day_5 = first_close_on_or_after(closes, (datetime.fromisoformat(meeting_date) + timedelta(days=5)).date().isoformat())
            if not entry:
                enriched.append(item | {"market_error": "no close near meeting date"})
                continue
            entry_date, entry_close = entry
            output = item | {"market_entry_date": entry_date, "market_price_at_signal": round(entry_close, 4)}
            if day_1:
                output["price_reaction_1d"] = round((day_1[1] / entry_close - 1) * 100, 2)
            if day_5:
                output["price_reaction_5d"] = round((day_5[1] / entry_close - 1) * 100, 2)
            enriched.append(output)
        except Exception as exc:  # noqa: BLE001
            enriched.append(item | {"market_error": str(exc)})
    return enriched


def load_outcomes(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["document_id"]: row
            for row in csv.DictReader(handle)
            if row.get("document_id")
        }


def initialize_outcome_labels(
    history_dir: Path,
    ticker_map_path: Path,
    output_path: Path,
    limit: int = 50,
) -> list[dict]:
    existing = load_outcomes(output_path)
    ranked = rank_history(history_dir, ticker_map_path, limit=limit)
    rows = list(existing.values())
    seen = {row["document_id"] for row in rows}
    for item in ranked:
        document_id = item.get("document_id")
        if not document_id or document_id in seen:
            continue
        rows.append(
            {
                "document_id": document_id,
                "meeting_date": item.get("meeting_date") or "",
                "sponsor": item.get("sponsor") or "",
                "ticker": item.get("ticker") or "",
                "drug": "",
                "indication": "",
                "adcom_vote": "",
                "adcom_outcome": "",
                "fda_final_decision": "",
                "fda_decision_date": "",
                "outcome_source": "",
                "notes": "",
            }
        )
        seen.add(document_id)

    fieldnames = [
        "document_id",
        "meeting_date",
        "sponsor",
        "ticker",
        "drug",
        "indication",
        "adcom_vote",
        "adcom_outcome",
        "fda_final_decision",
        "fda_decision_date",
        "outcome_source",
        "notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def normalize_signal(signal: str) -> str:
    if signal in {"STRONG_POSITIVE", "POSITIVE"}:
        return "positive"
    if signal in {"STRONG_NEGATIVE", "NEGATIVE"}:
        return "negative"
    return "mixed"


def normalize_outcome(outcome: str) -> str:
    lower = outcome.strip().lower()
    if lower in {"positive", "pass", "approved", "approve", "yes", "favorable"}:
        return "positive"
    if lower in {"negative", "fail", "rejected", "reject", "no", "unfavorable", "crl"}:
        return "negative"
    return "unknown"


def mini_backtest(history_dir: Path, ticker_map_path: Path, outcome_path: Path) -> dict:
    outcomes = load_outcomes(outcome_path)
    ranked_by_id = {
        item["document_id"]: item
        for item in rank_history(history_dir, ticker_map_path)
        if item.get("document_id")
    }
    rows = []
    for document_id, outcome in outcomes.items():
        item = ranked_by_id.get(document_id)
        if not item:
            continue
        payload_path = Path(item["file"])
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        signal_payload = payload.get("signal") or {}
        if not signal_payload:
            continue
        signal = normalize_signal(signal_payload.get("label", ""))
        adcom_outcome = normalize_outcome(outcome.get("adcom_outcome", ""))
        fda_outcome = normalize_outcome(outcome.get("fda_final_decision", ""))
        target = adcom_outcome if adcom_outcome != "unknown" else fda_outcome
        if target == "unknown":
            continue
        correct = signal == target if signal != "mixed" else None
        rows.append(
            {
                "document_id": document_id,
                "title": item["title"],
                "ticker": item.get("ticker"),
                "signal": signal_payload.get("label"),
                "signal_bucket": signal,
                "probability": signal_payload.get("probability"),
                "confidence": signal_payload.get("confidence"),
                "target_outcome": target,
                "correct": correct,
                "value_score": item.get("value_score"),
            }
        )

    actionable = [row for row in rows if row["correct"] is not None]
    correct_count = sum(1 for row in actionable if row["correct"])
    return {
        "labeled_analyzed_count": len(rows),
        "actionable_count": len(actionable),
        "correct_count": correct_count,
        "accuracy": round(correct_count / len(actionable), 4) if actionable else None,
        "rows": rows,
    }
