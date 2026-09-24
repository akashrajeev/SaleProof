"""Settings, read once from the environment (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    serpapi_key: str
    daily_budget: int
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "saleproof.db"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"


def load_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    data_dir = Path(os.environ.get("SALEPROOF_DATA_DIR", ROOT / "data"))
    return Settings(
        serpapi_key=os.environ.get("SERPAPI_KEY", ""),
        daily_budget=int(os.environ.get("SALEPROOF_DAILY_BUDGET", "10")),
        data_dir=data_dir,
    )
