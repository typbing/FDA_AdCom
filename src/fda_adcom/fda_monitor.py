from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "FDA-AdCom-Monitor/0.1"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

FDA_HOST = "www.fda.gov"

DOCUMENT_INCLUDE_TERMS = [
    "briefing",
    "background package",
    "background material",
    "voting question",
    "final question",
    "draft question",
    "questions to the committee",
]

DOCUMENT_EXCLUDE_TERMS = [
    "agenda",
    "announcement",
    "disclosure",
    "federal register",
    "minutes",
    "presentation",
    "roster",
    "summary minutes",
    "transcript",
    "waiver",
    "webcast",
]

PAGE_INCLUDE_TERMS = [
    "advisory committee",
    "advisory-committee",
    "meeting announcement",
    "meeting materials",
    "briefing information",
    "briefing document",
    "committee calendar",
]

PAGE_EXCLUDE_TERMS = [
    "about-advisory-committees",
    "advisory-committee-membership",
    "applying-membership",
    "common-questions-and-answers",
    "public-conduct",
    "contact-fda",
    "jobs-and-training",
    "podcasts-and-news-feeds",
]


@dataclass(frozen=True)
class DocumentCandidate:
    title: str
    url: str
    source_page: str
    discovered_at: str

    @property
    def id(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return {"seen_urls": [], "runs": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        self.path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def unseen(self, candidates: list[DocumentCandidate]) -> list[DocumentCandidate]:
        state = self.load()
        seen = set(state.get("seen_urls", []))
        return [candidate for candidate in candidates if candidate.url not in seen]

    def mark_seen(self, candidate: DocumentCandidate, result_path: Path | None = None) -> None:
        state = self.load()
        seen = set(state.get("seen_urls", []))
        seen.add(candidate.url)
        state["seen_urls"] = sorted(seen)
        state.setdefault("runs", []).append(
            {
                "url": candidate.url,
                "title": candidate.title,
                "source_page": candidate.source_page,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "result_path": str(result_path) if result_path else None,
            }
        )
        self.save(state)


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def normalize_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return parsed._replace(fragment="", query="").geturl()


def is_fda_url(url: str) -> bool:
    return urlparse(url).netloc.lower() == FDA_HOST


def is_probable_pdf(url: str, text: str = "") -> bool:
    lower = f"{url} {text}".lower()
    return ".pdf" in lower or "/media/" in urlparse(url).path.lower() and "/download" in lower


def is_relevant_document(title: str, url: str) -> bool:
    lower = f"{title} {url}".lower()
    if not is_probable_pdf(url, title):
        return False
    if any(term in lower for term in DOCUMENT_EXCLUDE_TERMS):
        return False
    return any(term in lower for term in DOCUMENT_INCLUDE_TERMS)


def is_relevant_page(url: str, text: str = "") -> bool:
    if not is_fda_url(url):
        return False
    parsed = urlparse(url)
    path = parsed.path.lower()
    lower = f"{text} {path}".lower()
    if path.rstrip("/") == "/advisory-committees":
        return False
    if "/advisory-committees" not in path and "/media/" not in path:
        return False
    if any(term in lower for term in PAGE_EXCLUDE_TERMS):
        return False
    return any(term in lower for term in PAGE_INCLUDE_TERMS)


def is_high_priority_page(url: str, text: str = "") -> bool:
    path = urlparse(url).path.lower()
    lower = f"{text} {path}".lower()
    return any(
        term in lower
        for term in [
            "meeting announcement",
            "meeting materials",
            "briefing information",
            "briefing document",
            "advisory-committee-calendar/",
        ]
    )


def extract_links(html: str, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for link in soup.find_all("a", href=True):
        title = re.sub(r"\s+", " ", link.get_text(" ", strip=True))
        href = normalize_url(page_url, link["href"])
        if href:
            links.append((title, href))
    return links


def extract_documents_from_html(html: str, page_url: str, discovered_at: str) -> list[DocumentCandidate]:
    candidates: dict[str, DocumentCandidate] = {}
    for title, href in extract_links(html, page_url):
        if not is_relevant_document(title, href):
            continue
        candidates[href] = DocumentCandidate(
            title=title or Path(urlparse(href).path).name,
            url=href,
            source_page=page_url,
            discovered_at=discovered_at,
        )
    return sorted(candidates.values(), key=lambda item: item.url)


def discover_event_pages(
    calendar_url: str,
    recent_url: str,
    seed_urls: list[str] | None = None,
    max_pages: int = 80,
    delay_seconds: float = 0.15,
) -> list[str]:
    urls: set[str] = set()
    queue = [normalize_url(calendar_url, url) for url in (seed_urls or [calendar_url, recent_url])]
    visited: set[str] = set()

    while queue and len(visited) < max_pages:
        page_url = queue.pop(0)
        if not page_url or page_url in visited or not is_relevant_page(page_url):
            continue
        visited.add(page_url)
        urls.add(page_url)

        try:
            html = fetch_html(page_url)
        except requests.RequestException:
            continue

        for title, href in extract_links(html, page_url):
            if href in visited or href in queue:
                continue
            if is_relevant_page(href, title):
                if is_high_priority_page(href, title):
                    queue.insert(0, href)
                else:
                    queue.append(href)
        if delay_seconds:
            time.sleep(delay_seconds)

    return sorted(urls)


def discover_documents(
    calendar_url: str,
    recent_url: str,
    seed_urls: list[str] | None = None,
    max_pages: int = 80,
) -> list[DocumentCandidate]:
    candidates: dict[str, DocumentCandidate] = {}
    now = datetime.now(timezone.utc).isoformat()
    event_pages = discover_event_pages(calendar_url, recent_url, seed_urls=seed_urls, max_pages=max_pages)
    for event_url in event_pages:
        try:
            html = fetch_html(event_url)
        except requests.RequestException:
            continue
        for candidate in extract_documents_from_html(html, event_url, now):
            candidates[candidate.url] = candidate
    return sorted(candidates.values(), key=lambda item: item.url)


def download_pdf(candidate: DocumentCandidate, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate.title).strip("_")[:120]
    path = output_dir / f"{candidate.id}_{safe_title or 'briefing'}.pdf"
    response = requests.get(candidate.url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        raise ValueError(f"URL did not return a PDF: {candidate.url}")
    path.write_bytes(response.content)
    return path


def write_run_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def candidate_to_dict(candidate: DocumentCandidate) -> dict:
    return asdict(candidate) | {"id": candidate.id}
