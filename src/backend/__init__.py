"""PactPal Backend Package."""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path = Path(__file__).resolve().parents[2] / ".env") -> None:
    """Load KEY=VALUE pairs from the repo-root .env without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


if not os.environ.get("PACTPAL_SKIP_DOTENV"):
    _load_dotenv()
