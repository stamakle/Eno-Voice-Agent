from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from english_tech.config import APP_BASE_URL, AUTH_OUTBOX_ROOT


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthEmailOutbox:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or AUTH_OUTBOX_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def write_verification_email(self, *, email: str, display_name: str, token: str) -> Path:
        payload = {
            "kind": "email_verification",
            "email": email,
            "display_name": display_name,
            "token": token,
            "verification_url": f"{APP_BASE_URL}/verify-email?token={token}",
            "created_at": utc_now().isoformat(),
        }
        return self._write_payload(payload)

    def write_password_reset_email(self, *, email: str, display_name: str, token: str) -> Path:
        payload = {
            "kind": "password_reset",
            "email": email,
            "display_name": display_name,
            "token": token,
            "reset_url": f"{APP_BASE_URL}/reset-password?token={token}",
            "created_at": utc_now().isoformat(),
        }
        return self._write_payload(payload)

    def _write_payload(self, payload: dict) -> Path:
        created = utc_now()
        path = self.root / f"{created.strftime('%Y%m%dT%H%M%S')}_{payload['kind']}_{uuid4().hex[:10]}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        latest_path = self.root / f"latest_{payload['kind']}.json"
        latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
