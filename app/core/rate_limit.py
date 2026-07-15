"""In-memory, per-IP rate limiting + request-body size cap.

Why a hand-rolled limiter instead of a library: at ~1k users on a single
Render instance we only need a lightweight burst/DoS guard in front of the
unauthenticated auth endpoints and the expensive AI endpoints. The real cost
ceiling for AI is enforced separately by the per-user USD usage caps
(``app/billing/access.py``) and the global daily breaker
(``app/services/usage_guardrails.py``); this middleware just stops one IP from
hammering us.

Limits are per-worker (uvicorn workers don't share memory). That's fine for a
coarse guard — a client hitting N workers still can't exceed N x the limit, and
Render fronts us behind a single small instance today.

The client IP is read from ``X-Forwarded-For`` (Render's proxy always sets it);
we take the leftmost entry, which is the original client per the de-facto
convention.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


# (limit, window_seconds) per named bucket. Chosen generous enough that no
# legitimate human (even several sharing a carrier-NAT IP) trips them, but low
# enough to blunt scripted abuse.
_AUTH_EMAIL_LIMIT = 10          # anti brute-force on 6-digit email codes
_AUTH_EMAIL_WINDOW = 300        # per 5 minutes
_AUTH_LIMIT = 30               # apple/google/verify/link
_AUTH_WINDOW = 300
_AGENT_LIMIT = 60              # expensive LLM endpoints (per minute)
_AGENT_WINDOW = 60
_DEFAULT_LIMIT = 240          # everything else (per minute)
_DEFAULT_WINDOW = 60

# How often (seconds) to sweep empty/stale keys so the store can't grow
# unbounded from one-off scanners hitting many paths.
_SWEEP_INTERVAL = 300


def client_ip_from_request(request: Request) -> str:
    """Best-effort real client IP, preferring proxy-forwarded headers."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Coarse per-IP rate limit + Content-Length guard.

    Runs before route handlers. ``/health`` is always exempt so Render's probe
    is never throttled.
    """

    def __init__(self, app, *, enabled: bool = True, max_body_bytes: int = 15 * 1024 * 1024):
        super().__init__(app)
        self.enabled = enabled
        self.max_body_bytes = max_body_bytes
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    @staticmethod
    def _bucket(path: str) -> Tuple[str, int, int]:
        if path.startswith("/auth/email"):
            return ("auth_email", _AUTH_EMAIL_LIMIT, _AUTH_EMAIL_WINDOW)
        if path.startswith("/auth/"):
            return ("auth", _AUTH_LIMIT, _AUTH_WINDOW)
        if path.startswith("/app/agent/run") or path == "/agent/run" or path.startswith("/ai/"):
            return ("agent", _AGENT_LIMIT, _AGENT_WINDOW)
        return ("default", _DEFAULT_LIMIT, _DEFAULT_WINDOW)

    def _sweep(self, now: float) -> None:
        stale = [k for k, dq in self._hits.items() if not dq or now - dq[-1] > max(_AUTH_WINDOW, _DEFAULT_WINDOW)]
        for k in stale:
            self._hits.pop(k, None)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if path == "/health":
            return await call_next(request)

        # Body-size guard (cheap header check; blocks oversized uploads before
        # we buffer them into memory).
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > self.max_body_bytes:
            logger.warning("[RATELIMIT] body too large path=%s len=%s", path, content_length)
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})

        bucket, limit, window = self._bucket(path)
        ip = client_ip_from_request(request)
        key = (bucket, ip)
        now = time.monotonic()

        dq = self._hits[key]
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= limit:
            retry_after = int(window - (now - dq[0])) + 1 if dq else window
            logger.warning(
                "[RATELIMIT] throttled path=%s ip=%s bucket=%s limit=%s/%ss",
                path, ip, bucket, limit, window,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        dq.append(now)

        if now - self._last_sweep > _SWEEP_INTERVAL:
            self._sweep(now)
            self._last_sweep = now

        return await call_next(request)
