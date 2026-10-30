"""Environment-driven settings. Credentials never leave the server."""
from __future__ import annotations

import os
from dataclasses import dataclass

SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"


@dataclass(frozen=True)
class Settings:
    mode: str
    client_id: str | None
    client_secret: str | None
    mandate_secret: str

    @property
    def live(self) -> bool:
        return self.mode == "live"


def load_settings() -> Settings:
    mode = os.environ.get("PAYPAL_MODE", "mock")
    if mode not in ("mock", "live"):
        raise ValueError(f"PAYPAL_MODE must be mock or live, got {mode!r}")
    settings = Settings(
        mode=mode,
        client_id=os.environ.get("PAYPAL_CLIENT_ID") or None,
        client_secret=os.environ.get("PAYPAL_CLIENT_SECRET") or None,
        mandate_secret=os.environ.get("PACTPAL_MANDATE_SECRET", ""),
    )
    if settings.live and not (settings.client_id and settings.client_secret):
        raise ValueError("live mode needs PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET")
    if len(settings.mandate_secret) < 32:
        raise ValueError("PACTPAL_MANDATE_SECRET must be at least 32 characters")
    return settings
