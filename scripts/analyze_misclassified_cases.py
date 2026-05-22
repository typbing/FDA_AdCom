#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "data" / "history_runs"
RUNS_DIR = ROOT / "data" / "runs"
OUTCOME_PATH = ROOT / "data" / "outcome_labels.csv"
OUTPUT_PATH = RUNS_DIR / "misclassification_case_studies.md"


def load_json_files(*dirs: Path) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict):
                records.append((path, payload))
    return records


def load_outcomes() -> dict[str, dict[str, str]]:
    import csv

    if not OUTCOME_PATH.exists():
        return {}
    with OUTCOME_PATH.open(newline="", encoding="utf-8") as handle:
        return {
            row.get("document_id", ""): row
            for row in csv.DictReader(handle)
            if row.get("document_id")
        }


def text_blob(payload: dict) -> str:
    pieces = []
    document = payload.get("document", {})
    pieces.extend(str(document.get(key, "")) for key in ["id", "title", "url", "source_page"])
    signal = payload.get("signal", {})
    analysis = payload.get("analysis", {})
    pieces.extend(str(signal.get(key, "")) for key in ["label", "rationale"])
    pieces.extend(str(analysis.get(key, "")) for key in ["key_concerns", "key_positives", "raw"])
    return " ".join(pieces).lower()


def find_case(records: list[tuple[Path, dict]], terms: list[str]) -> tuple[Path, dict] | None:
    lowered = [term.lower() for term in terms]
    matches = []
    for path, payload in records:
        blob = text_blob(payload)
        if any(term in blob for term in lowered):
            score = sum(term in blob for term in lowered)
            has_signal = bool(payload.get("signal"))
            matches.append((score, has_signal, path, payload))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[1], item[0], str(item[2])), reverse=True)
    return matches[0][2], matches[0][3]


def list_text(values: object) -> str:
    if isinstance(values, list) and values:
        return "\n".join(f"- {value}" for value in values)
    if values:
        return f"- {values}"
    return "Insufficient local data. TODO_SOURCE_NEEDED."


def outcome_text(payload: dict, outcomes: dict[str, dict[str, str]]) -> str:
    document_id = str(payload.get("document", {}).get("id", ""))
    row = outcomes.get(document_id, {})
    parts = []
    for field in ["adcom_vote", "adcom_outcome", "fda_final_decision", "fda_decision_date", "outcome_source", "notes"]:
        value = str(row.get(field, "")).strip()
        if value:
            parts.append(f"- {field}: {value}")
    return "\n".join(parts) if parts else "Insufficient local data. TODO_SOURCE_NEEDED."


def case_section(title: str, found: tuple[Path, dict] | None, outcomes: dict[str, dict[str, str]]) -> str:
    if not found:
        return f"""## {title}

### Model Signal
Insufficient local data. TODO_SOURCE_NEEDED.

### Model Probability
Insufficient local data. TODO_SOURCE_NEEDED.

### Model Confidence
Insufficient local data. TODO_SOURCE_NEEDED.

### Key Concerns Extracted by Model
Insufficient local data. TODO_SOURCE_NEEDED.

### Key Positives Extracted by Model
Insufficient local data. TODO_SOURCE_NEEDED.

### Why the Model Likely Overreacted
Insufficient local data. TODO_SOURCE_NEEDED.

### Final Regulatory Outcome
Insufficient local data. TODO_SOURCE_NEEDED.

### Why Final Outcome Diverged from Harsh FDA Tone
Insufficient local data. TODO_SOURCE_NEEDED.

### Features That Should Have Helped
Insufficient local data. TODO_SOURCE_NEEDED.

### Proposed Prompt Fix
Insufficient local data. TODO_SOURCE_NEEDED.

### Proposed Signal Rule Fix
Insufficient local data. TODO_SOURCE_NEEDED.
"""

    path, payload = found
    signal = payload.get("signal", {})
    analysis = payload.get("analysis", {})
    raw = analysis.get("raw", {}) if isinstance(analysis.get("raw"), dict) else {}
    concerns = analysis.get("key_concerns") or raw.get("key_concerns")
    positives = analysis.get("key_positives") or raw.get("key_positives")
    probability = signal.get("raw_probability", signal.get("probability", analysis.get("approval_probability_estimate")))
    confidence = signal.get("confidence", analysis.get("confidence"))

    return f"""## {title}

Source JSON: `{path.relative_to(ROOT)}`

### Model Signal
{signal.get("label", "Insufficient local data. TODO_SOURCE_NEEDED.")}

### Model Probability
{probability if probability not in [None, ""] else "Insufficient local data. TODO_SOURCE_NEEDED."}

### Model Confidence
{confidence if confidence not in [None, ""] else "Insufficient local data. TODO_SOURCE_NEEDED."}

### Key Concerns Extracted by Model
{list_text(concerns)}

### Key Positives Extracted by Model
{list_text(positives)}

### Why the Model Likely Overreacted
The local record suggests the model weighted FDA risk language more heavily than contextual approval factors. This should be validated against primary sources before treating it as a final lesson.

### Final Regulatory Outcome
{outcome_text(payload, outcomes)}

### Why Final Outcome Diverged from Harsh FDA Tone
Insufficient local data. TODO_SOURCE_NEEDED.

### Features That Should Have Helped
- document_type
- unmet_need_score
- regulatory_flexibility
- safety_manageability
- advisory_question_polarity
- likely_panel_vote_direction

### Proposed Prompt Fix
Require the model to separate FDA critical tone from endpoint success, safety manageability, unmet need, regulatory flexibility, likely panel vote, and final FDA approval probability.

### Proposed Signal Rule Fix
Apply FDA briefing de-noising and positive adjustments for high unmet need, high regulatory flexibility, and manageable safety risks before mapping to final signal.
"""


def main() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    records = load_json_files(HISTORY_DIR, RUNS_DIR)
    outcomes = load_outcomes()
    regn = find_case(records, ["REGN", "EYLEA", "ROP", "aflibercept", "retinopathy of prematurity"])
    opill = find_case(records, ["Opill", "PRGO", "Perrigo", "norgestrel", "HRA Pharma"])

    report = f"""# Misclassification Case Studies

{case_section("Case 1: REGN / EYLEA ROP", regn, outcomes)}

{case_section("Case 2: Opill", opill, outcomes)}

## General Lessons

- FDA briefing tone is structurally critical and risk-focused.
- Harsh FDA language does not automatically imply rejection.
- Risk can be acceptable if it is manageable through labeling, REMS, restricted use, or monitoring.
- High unmet need, rare disease context, public health value, and lack of alternatives can create regulatory flexibility.
- The model must distinguish AdCom vote direction from final FDA approval probability.
"""
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
