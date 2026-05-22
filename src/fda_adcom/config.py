from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SEED_URLS = [
    "https://www.fda.gov/advisory-committees/advisory-committee-calendar",
    "https://www.fda.gov/advisory-committees/recently-updated-advisory-committee-materials",
    "https://www.fda.gov/advisory-committees/committees-and-meeting-materials/human-drug-advisory-committees",
    "https://www.fda.gov/advisory-committees/committees-and-meeting-materials/blood-vaccines-and-other-biologics",
    "https://www.fda.gov/advisory-committees/committees-and-meeting-materials/medical-devices",
    "https://www.fda.gov/advisory-committees/committees-and-meeting-materials",
]


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    calendar_url: str
    recent_url: str
    seed_urls: list[str]
    crawl_max_pages: int
    poll_seconds: int
    data_dir: Path
    ai_provider: str
    ai_model: str
    ai_timeout_seconds: int
    openai_api_key: str
    anthropic_api_key: str
    deepseek_api_key: str
    deepseek_base_url: str
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        calendar_url = os.getenv(
            "FDA_CALENDAR_URL",
            "https://www.fda.gov/advisory-committees/advisory-committee-calendar",
        )
        recent_url = os.getenv(
            "FDA_RECENT_URL",
            "https://www.fda.gov/advisory-committees/recently-updated-advisory-committee-materials",
        )
        seed_urls = [
            url.strip()
            for url in os.getenv("FDA_SEED_URLS", ",".join(DEFAULT_SEED_URLS)).split(",")
            if url.strip()
        ]
        for required_url in [*DEFAULT_SEED_URLS, calendar_url, recent_url]:
            if required_url not in seed_urls:
                seed_urls.append(required_url)
        return cls(
            calendar_url=calendar_url,
            recent_url=recent_url,
            seed_urls=seed_urls,
            crawl_max_pages=int(os.getenv("FDA_CRAWL_MAX_PAGES", "80")),
            poll_seconds=int(os.getenv("FDA_POLL_SECONDS", "60")),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            ai_provider=os.getenv("AI_PROVIDER", "heuristic").lower(),
            ai_model=os.getenv("AI_MODEL", ""),
            ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "120")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", os.getenv("Deepseek_API_KEY", "")),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "raw_pdfs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "runs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "history_pdfs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "history_runs").mkdir(parents=True, exist_ok=True)
