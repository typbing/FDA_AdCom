#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTCOME_PATH = ROOT / "data" / "outcome_labels.csv"
HISTORY_DIR = ROOT / "data" / "history_runs"
REPORT_PATH = ROOT / "data" / "runs" / "release_date_inference_audit.json"
USER_AGENT = "Mozilla/5.0 FDA-AdCom-Monitor/0.1"

RELEASE_FIELDS = [
    "briefing_pdf_release_date",
    "briefing_pdf_release_date_source",
    "briefing_pdf_release_date_confidence",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_fields(fieldnames: list[str], rows: list[dict[str, str]]) -> list[str]:
    output = list(fieldnames)
    insert_after = "fda_decision_date"
    insert_at = output.index(insert_after) + 1 if insert_after in output else len(output)
    for field in RELEASE_FIELDS:
        if field not in output:
            output.insert(insert_at, field)
            insert_at += 1
        for row in rows:
            row.setdefault(field, "")
    return output


def parse_pdf_date(value: object) -> str | None:
    text = clean(value)
    match = re.match(r"D:(\d{4})(\d{2})(\d{2})", text)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return datetime(int(year), int(month), int(day)).date().isoformat()
    except ValueError:
        return None


def load_history(document_id: str) -> dict:
    path = HISTORY_DIR / f"{document_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def find_pdf_path(document_id: str, payload: dict) -> Path | None:
    raw_pdf_path = clean(payload.get("pdf_path"))
    if raw_pdf_path:
        pdf_path = Path(raw_pdf_path)
        if pdf_path.exists() and pdf_path.is_file():
            return pdf_path
    for directory in [ROOT / "data" / "history_pdfs", ROOT / "data" / "raw_pdfs", ROOT / "data" / "sample_pdfs"]:
        matches = sorted(directory.glob(f"{document_id}_*.pdf"))
        if matches:
            return matches[0]
    return None


def pdf_metadata_date(pdf_path: Path) -> tuple[str | None, str]:
    reader = PdfReader(str(pdf_path))
    metadata = reader.metadata or {}
    for field in ["/CreationDate", "/ModDate"]:
        date_text = parse_pdf_date(metadata.get(field))
        if date_text:
            return date_text, f"PDF metadata {field}"
    return None, ""


def media_last_modified(url: str) -> str | None:
    if not url:
        return None
    response = requests.head(
        url,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    header = response.headers.get("Last-Modified")
    if not header:
        return None
    parsed = parsedate_to_datetime(header)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.date().isoformat()


def plausible_release_date(candidate: str, meeting_date: str) -> bool:
    if not candidate or not meeting_date:
        return True
    candidate_day = datetime.fromisoformat(candidate).date()
    meeting_day = datetime.fromisoformat(meeting_date).date()
    delta = (meeting_day - candidate_day).days
    return 0 <= delta <= 21


def infer_date(row: dict[str, str], use_head: bool) -> dict:
    document_id = clean(row.get("document_id"))
    meeting_date = clean(row.get("meeting_date"))
    payload = load_history(document_id)
    document = payload.get("document", {})
    pdf_path = find_pdf_path(document_id, payload)

    result = {
        "document_id": document_id,
        "ticker": clean(row.get("ticker")),
        "meeting_date": meeting_date,
        "inferred_date": "",
        "source": "",
        "confidence": "",
        "status": "missing_pdf",
    }

    if pdf_path:
        result["status"] = "missing_pdf_metadata_date"
        try:
            date_text, source = pdf_metadata_date(pdf_path)
        except Exception as exc:  # noqa: BLE001
            result["status"] = f"metadata_error: {exc}"
            date_text, source = None, ""
        if date_text and plausible_release_date(date_text, meeting_date):
            result.update(
                {
                    "inferred_date": date_text,
                    "source": source,
                    "confidence": "medium",
                    "status": "inferred_from_pdf_metadata",
                }
            )
            return result
        if date_text:
            result.update(
                {
                    "inferred_date": date_text,
                    "source": source,
                    "confidence": "low",
                    "status": "metadata_date_outside_meeting_window",
                }
            )

    if use_head:
        try:
            head_date = media_last_modified(clean(document.get("url")))
        except Exception as exc:  # noqa: BLE001
            result["status"] = f"head_error: {exc}"
            head_date = None
        if head_date and plausible_release_date(head_date, meeting_date):
            result.update(
                {
                    "inferred_date": head_date,
                    "source": "media Last-Modified header",
                    "confidence": "low",
                    "status": "inferred_from_last_modified",
                }
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--head-fallback", action="store_true")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    fieldnames, rows = read_rows(OUTCOME_PATH)
    fieldnames = ensure_fields(fieldnames, rows)
    results = []

    for row in rows:
        if clean(row.get("briefing_pdf_release_date")) and not args.overwrite:
            results.append(
                {
                    "document_id": row.get("document_id", ""),
                    "ticker": row.get("ticker", ""),
                    "meeting_date": row.get("meeting_date", ""),
                    "inferred_date": row.get("briefing_pdf_release_date", ""),
                    "source": row.get("briefing_pdf_release_date_source", "existing"),
                    "confidence": row.get("briefing_pdf_release_date_confidence", ""),
                    "status": "already_present",
                }
            )
            continue

        result = infer_date(row, use_head=args.head_fallback)
        results.append(result)
        if args.update and result["status"].startswith("inferred_"):
            row["briefing_pdf_release_date"] = result["inferred_date"]
            row["briefing_pdf_release_date_source"] = result["source"]
            row["briefing_pdf_release_date_confidence"] = result["confidence"]

    report = {
        "total_rows": len(rows),
        "inferred_count": sum(1 for result in results if result["status"].startswith("inferred_")),
        "already_present": sum(1 for result in results if result["status"] == "already_present"),
        "status_counts": {
            status: sum(1 for result in results if result["status"] == status)
            for status in sorted({result["status"] for result in results})
        },
        "results": results,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.update:
        write_rows(OUTCOME_PATH, fieldnames, rows)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
