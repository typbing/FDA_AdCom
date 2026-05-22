from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from fda_adcom.analyzer import analyze_sections
from fda_adcom.config import Settings
from fda_adcom.fda_monitor import (
    DocumentCandidate,
    StateStore,
    candidate_to_dict,
    discover_documents,
    download_pdf,
    write_run_result,
)
from fda_adcom.history import rank_history
from fda_adcom.notify import notify_console, notify_telegram
from fda_adcom.pdf_parser import parse_pdf
from fda_adcom.signals import generate_signal


def process_pdf(settings: Settings, pdf_path: Path, candidate: DocumentCandidate | None = None) -> dict:
    parsed = parse_pdf(pdf_path)
    analysis = analyze_sections(
        settings.ai_provider,
        settings.ai_model,
        parsed.sections,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_base_url=settings.deepseek_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
    )
    signal = generate_signal(analysis)
    document = (
        candidate_to_dict(candidate)
        if candidate
        else {
            "id": pdf_path.stem,
            "title": pdf_path.name,
            "url": str(pdf_path),
            "source_page": "local",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {
        "document": document,
        "pdf_path": str(pdf_path),
        "page_count": parsed.page_count,
        "sections_found": sorted(parsed.sections),
        "analysis": analysis.to_dict(),
        "signal": signal.to_dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def run_once(settings: Settings, dry_run: bool = False) -> list[dict]:
    settings.ensure_dirs()
    store = StateStore(settings.data_dir / "state.json")
    candidates = discover_documents(
        settings.calendar_url,
        settings.recent_url,
        seed_urls=settings.seed_urls,
        max_pages=settings.crawl_max_pages,
    )
    unseen = store.unseen(candidates)
    results = []

    for candidate in unseen:
        if dry_run:
            payload = {
                "document": candidate_to_dict(candidate),
                "dry_run": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            notify_console(payload | {"signal": {"label": "NEW_DOC"}, "analysis": {"provider": "none"}})
            results.append(payload)
            continue

        pdf_path = download_pdf(candidate, settings.data_dir / "raw_pdfs")
        payload = process_pdf(settings, pdf_path, candidate)
        result_path = settings.data_dir / "runs" / f"{candidate.id}.json"
        write_run_result(result_path, payload)
        store.mark_seen(candidate, result_path)
        notify_console(payload)
        notify_telegram(payload, settings.telegram_bot_token, settings.telegram_chat_id)
        results.append(payload)

    return results


def bootstrap_seen(settings: Settings, max_pages: int | None = None) -> list[dict]:
    settings.ensure_dirs()
    store = StateStore(settings.data_dir / "state.json")
    candidates = discover_documents(
        settings.calendar_url,
        settings.recent_url,
        seed_urls=settings.seed_urls,
        max_pages=max_pages or settings.crawl_max_pages,
    )
    unseen = store.unseen(candidates)
    for candidate in unseen:
        store.mark_seen(candidate)
    return [candidate_to_dict(candidate) for candidate in unseen]


def is_fda_briefing_candidate(candidate: DocumentCandidate) -> bool:
    lower = candidate.title.lower()
    return "fda" in lower and ("briefing" in lower or "background" in lower)


def backfill_history(
    settings: Settings,
    max_pages: int | None = None,
    limit: int | None = None,
    fda_only: bool = True,
    skip_existing: bool = True,
    analyze: bool = False,
) -> list[dict]:
    settings.ensure_dirs()
    candidates = discover_documents(
        settings.calendar_url,
        settings.recent_url,
        seed_urls=settings.seed_urls,
        max_pages=max_pages or settings.crawl_max_pages,
    )
    if fda_only:
        candidates = [candidate for candidate in candidates if is_fda_briefing_candidate(candidate)]

    results: list[dict] = []
    selected: list[DocumentCandidate] = []
    for candidate in candidates:
        result_path = settings.data_dir / "history_runs" / f"{candidate.id}.json"
        if skip_existing and result_path.exists():
            continue
        selected.append(candidate)
        if limit is not None and len(selected) >= limit:
            break

    for candidate in selected:
        result_path = settings.data_dir / "history_runs" / f"{candidate.id}.json"
        try:
            pdf_path = download_pdf(candidate, settings.data_dir / "history_pdfs")
            if analyze:
                payload = process_pdf(settings, pdf_path, candidate)
            else:
                parsed = parse_pdf(pdf_path)
                payload = {
                    "document": candidate_to_dict(candidate),
                    "pdf_path": str(pdf_path),
                    "page_count": parsed.page_count,
                    "sections_found": sorted(parsed.sections),
                    "section_lengths": {
                        section_name: len(section_text)
                        for section_name, section_text in parsed.sections.items()
                    },
                    "analysis_status": "metadata_only",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as exc:  # noqa: BLE001
            payload = {
                "document": candidate_to_dict(candidate),
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        write_run_result(result_path, payload)
        results.append(payload | {"result_path": str(result_path)})

    return results


def analyze_ranked_history(
    settings: Settings,
    limit: int = 1,
    min_score: int = 70,
) -> list[dict]:
    settings.ensure_dirs()
    ranked = rank_history(
        settings.data_dir / "history_runs",
        settings.data_dir / "sponsor_tickers.csv",
    )
    selected = [
        item
        for item in ranked
        if item.get("value_score", 0) >= min_score and not item.get("has_ai_analysis")
    ][:limit]

    results: list[dict] = []
    for item in selected:
        result_path = Path(item["file"])
        try:
            payload = json_load(result_path)
            pdf_path = Path(payload["pdf_path"])
            candidate = DocumentCandidate(
                title=payload["document"]["title"],
                url=payload["document"]["url"],
                source_page=payload["document"]["source_page"],
                discovered_at=payload["document"].get("discovered_at", ""),
            )
            analyzed = process_pdf(settings, pdf_path, candidate)
            analyzed["history_rank"] = item
            write_run_result(result_path, analyzed)
            results.append(analyzed | {"result_path": str(result_path)})
        except Exception as exc:  # noqa: BLE001
            error_payload = {
                "history_rank": item,
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            write_run_result(result_path, error_payload)
            results.append(error_payload | {"result_path": str(result_path)})
    return results


def json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def watch(settings: Settings) -> None:
    while True:
        try:
            run_once(settings)
        except Exception as exc:  # noqa: BLE001
            print(f"Pipeline error: {exc}")
        time.sleep(settings.poll_seconds)
