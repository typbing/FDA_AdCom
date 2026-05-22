#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTCOME_PATH = ROOT / "data" / "outcome_labels.csv"
HISTORY_DIR = ROOT / "data" / "history_runs"
BACKTEST_PATH = ROOT / "data" / "runs" / "mini_backtest_v2.json"

CRITICAL_FIELDS = [
    "drug",
    "indication",
    "adcom_vote",
    "adcom_outcome",
    "fda_final_decision",
    "fda_decision_date",
    "outcome_source",
]

EXPECTED_COLUMNS = [
    "document_id",
    "meeting_date",
    "sponsor",
    "ticker",
    *CRITICAL_FIELDS,
    "notes",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def warn(message: str) -> None:
    print(f"WARNING: {message}")


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        warn(f"Missing file: {path}")
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                warn(f"No header row found in {path}")
                return []
            missing_columns = [column for column in EXPECTED_COLUMNS if column not in reader.fieldnames]
            if missing_columns:
                warn(f"{path} is missing columns: {', '.join(missing_columns)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        warn(f"Unable to read {path}: {exc}")
        return []


def history_ids(path: Path) -> set[str]:
    if not path.exists():
        warn(f"Missing directory: {path}")
        return set()
    ids: set[str] = set()
    for item in path.glob("*.json"):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warn(f"Skipping unreadable history JSON {item}: {exc}")
            continue
        document_id = clean(payload.get("document", {}).get("id")) or item.stem
        ids.add(document_id)
    return ids


def load_backtest(path: Path) -> dict:
    if not path.exists():
        warn(f"Missing file: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        warn(f"Unable to read {path}: {exc}")
        return {}


def is_missing(row: dict[str, str], field: str) -> bool:
    value = clean(row.get(field))
    return not value


def has_todo(row: dict[str, str]) -> bool:
    return "TODO" in clean(row.get("notes")).upper() or "TODO" in clean(row.get("outcome_source")).upper()


def fully_labeled(row: dict[str, str]) -> bool:
    return all(not is_missing(row, field) for field in CRITICAL_FIELDS) and not has_todo(row)


def partially_labeled(row: dict[str, str]) -> bool:
    filled = [field for field in CRITICAL_FIELDS if not is_missing(row, field)]
    return bool(filled) and not fully_labeled(row)


def completely_unlabeled(row: dict[str, str]) -> bool:
    return all(is_missing(row, field) for field in CRITICAL_FIELDS)


def normalize_text(*values: str) -> str:
    return " ".join(clean(value).lower() for value in values if clean(value))


def classify_outcome(row: dict[str, str]) -> str:
    text = normalize_text(
        row.get("adcom_vote", ""),
        row.get("adcom_outcome", ""),
        row.get("fda_final_decision", ""),
        row.get("notes", ""),
    )
    if not text:
        return "unknown"
    if "withdraw" in text:
        return "withdrawn"
    if any(term in text for term in ["split", "mixed", "narrow"]):
        return "mixed"
    if any(term in text for term in ["negative", "rejected", "reject", "crl", "complete response", "unfavorable"]):
        return "negative"
    if any(term in text for term in ["positive", "approved", "approve", "favorable"]):
        return "positive"
    return "unknown"


def print_missing_list(rows: Iterable[dict[str, str]], field: str) -> None:
    print(f"- Missing {field}:")
    missing = [row for row in rows if is_missing(row, field)]
    if not missing:
        print("  - None")
        return
    for row in missing:
        print(
            "  - "
            f"{clean(row.get('document_id')) or 'UNKNOWN'} | "
            f"{clean(row.get('ticker')) or ''} | "
            f"{clean(row.get('drug')) or ''} | "
            f"{clean(row.get('indication')) or ''}"
        )


def main() -> None:
    rows = load_rows(OUTCOME_PATH)
    history = history_ids(HISTORY_DIR)
    backtest = load_backtest(BACKTEST_PATH)

    matching_history = sum(1 for row in rows if clean(row.get("document_id")) in history)
    missing_counts = {field: sum(1 for row in rows if is_missing(row, field)) for field in CRITICAL_FIELDS}
    outcome_counts = {"positive": 0, "negative": 0, "mixed": 0, "withdrawn": 0, "unknown": 0}
    for row in rows:
        outcome_counts[classify_outcome(row)] += 1

    print("=== FDA AdCom Data Audit Report ===")
    print()
    print(f"Total Rows in outcome_labels.csv: {len(rows)}")
    print(f"History Run JSON Files: {len(history)}")
    print(f"Rows With Matching History Runs: {matching_history}")
    print(f"Fully Labeled Rows: {sum(1 for row in rows if fully_labeled(row))}")
    print(f"Partially Labeled Rows: {sum(1 for row in rows if partially_labeled(row))}")
    print(f"Completely Unlabeled Rows: {sum(1 for row in rows if completely_unlabeled(row))}")
    print()
    print("[Missing Label Gaps]")
    for field, count in missing_counts.items():
        print(f"- Missing {field}: {count}")
    print()
    print("[Rows Missing Critical Fields]")
    for field in ["adcom_vote", "fda_final_decision", "fda_decision_date", "outcome_source"]:
        print_missing_list(rows, field)
    print()
    print("[Outcome Distribution]")
    print(f"- Positive / Approved: {outcome_counts['positive']}")
    print(f"- Negative / Rejected / CRL: {outcome_counts['negative']}")
    print(f"- Mixed / Split Vote: {outcome_counts['mixed']}")
    print(f"- Withdrawn: {outcome_counts['withdrawn']}")
    print(f"- Unknown / TODO: {outcome_counts['unknown']}")
    print()
    print("[Mini Backtest v2 Summary]")
    print(f"- labeled_analyzed_count: {backtest.get('labeled_analyzed_count', 'WARNING_MISSING')}")
    print(f"- actionable_count: {backtest.get('actionable_count', 'WARNING_MISSING')}")
    print(f"- correct_count: {backtest.get('correct_count', 'WARNING_MISSING')}")
    print(f"- accuracy: {backtest.get('accuracy', 'WARNING_MISSING')}")
    print()
    print("[Recommended Next Labeling Priority]")
    print("1. Rows with signal but missing final FDA decision")
    print("2. Rows with negative or mixed AdCom vote")
    print(
        "3. Rows involving CRL, withdrawal, safety concerns, surrogate endpoint disputes, "
        "failed endpoint, or narrow/split vote"
    )


if __name__ == "__main__":
    main()
