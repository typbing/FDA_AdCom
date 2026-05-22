from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedDocument:
    path: str
    page_count: int
    text: str
    sections: dict[str, str]


SECTION_HEADINGS = {
    "executive_summary": [
        "executive summary",
        "summary",
        "fda executive summary",
    ],
    "background": [
        "background",
        "regulatory background",
    ],
    "efficacy": [
        "efficacy issues",
        "clinical efficacy",
        "clinical efficacy assessment",
        "efficacy",
        "effectiveness",
    ],
    "safety": [
        "safety issues",
        "clinical safety",
        "safety summary",
        "safety",
    ],
    "questions": [
        "questions to the committee",
        "voting question",
        "discussion question",
        "points for discussion",
        "draft points for consideration",
    ],
}


def extract_text(pdf_path: str | Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append(f"\n\n[PAGE {index}]\n{page_text}")
    return "\n".join(pages), len(reader.pages)


def normalize_heading(line: str) -> str:
    line = re.sub(r"^\s*\d+(\.\d+)*\s+", "", line)
    line = re.sub(r"[^A-Za-z ]+", " ", line)
    return re.sub(r"\s+", " ", line).strip().lower()


def find_heading_positions(text: str) -> list[tuple[int, str]]:
    positions: list[tuple[int, str]] = []
    for match in re.finditer(r"(?m)^[ \t]*(.{3,90})[ \t]*$", text):
        raw_line = match.group(1)
        if "..." in raw_line or raw_line.strip().startswith("[PAGE"):
            continue
        normalized = normalize_heading(raw_line)
        for section_name, headings in SECTION_HEADINGS.items():
            if normalized in headings:
                positions.append((match.start(), section_name))
                break
            if any(normalized.startswith(heading) for heading in headings):
                positions.append((match.start(), section_name))
                break
    return sorted(positions, key=lambda item: item[0])


def split_sections(text: str) -> dict[str, str]:
    positions = find_heading_positions(text)
    sections: dict[str, str] = {}
    for index, (start, section_name) in enumerate(positions):
        end = len(text)
        for next_start, next_section_name in positions[index + 1 :]:
            if next_section_name != section_name:
                end = next_start
                break
        chunk = text[start:end].strip()
        if chunk and section_name not in sections:
            sections[section_name] = chunk[:120_000]

    if "questions" not in sections:
        questions_match = re.search(
            r"(?is)(questions?\s+(to|for)\s+the\s+committee.*)$", text[-80_000:]
        )
        if questions_match:
            sections["questions"] = questions_match.group(1).strip()[:80_000]

    if "executive_summary" not in sections:
        sections["executive_summary"] = text[:30_000].strip()

    return sections


def parse_pdf(pdf_path: str | Path) -> ParsedDocument:
    text, page_count = extract_text(pdf_path)
    return ParsedDocument(
        path=str(pdf_path),
        page_count=page_count,
        text=text,
        sections=split_sections(text),
    )
