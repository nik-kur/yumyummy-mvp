"""
Lightweight HMAC-signed tokens for linking Gumroad purchases to
Telegram user IDs.  No external dependencies beyond stdlib.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any


def create_claim_token(
    telegram_id: str,
    plan_id: str,
    secret_key: str,
    ttl_seconds: int = 3600,
) -> str:
    payload = {
        "tid": telegram_id,
        "pid": plan_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    data = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{data}.{sig}"


def verify_claim_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    """
    Verify a claim token and return its payload, or None if invalid/expired.
    """
    parts = token.split(".")
    if len(parts) != 2:
        return None

    data, sig = parts
    expected_sig = hmac.new(secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected_sig):
        return None

    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding

    try:
        payload = json.loads(base64.urlsafe_b64decode(data))
    except (json.JSONDecodeError, Exception):
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return payload
