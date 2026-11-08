from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    AUTH_RATE_LIMIT_PER_MIN,
    IP_ALLOWLIST,
    IS_PROD,
    TRUSTED_ORIGINS,
)

log = logging.getLogger("omt.security")

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_AUTH_PATHS = {
    "/auth/login",
    "/auth/callback",
    "/auth/dev-login",
    "/auth/logout",
}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _ip_allowed(ip: str) -> bool:
    if not IP_ALLOWLIST:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in IP_ALLOWLIST:
        try:
            if "/" in item:
                if addr in ipaddress.ip_network(item, strict=False):
                    return True
            elif addr == ipaddress.ip_address(item):
                return True
        except ValueError:
            continue
    return False


class _RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = max(per_minute, 1)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        window = 60.0
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


_auth_limiter = _RateLimiter(AUTH_RATE_LIMIT_PER_MIN)


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        # Same-site navigations / curl without Origin — allow with SameSite cookie
        return True
    if origin in TRUSTED_ORIGINS:
        return True
    # Allow same host as request URL
    host = request.headers.get("host")
    if host and origin.rstrip("/").endswith(host):
        return True
    return False


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = _client_ip(request)
        if not _ip_allowed(ip):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)

        path = request.url.path
        if path in _AUTH_PATHS or path.startswith("/auth/"):
            if not _auth_limiter.allow(f"auth:{ip}"):
                return JSONResponse(
                    {"detail": "Too many auth requests — try again later"},
                    status_code=429,
                )

        if request.method not in _SAFE_METHODS and path.startswith(("/api/", "/auth/")):
            if not _origin_ok(request):
                log.warning("blocked cross-origin %s %s from %s", request.method, path, ip)
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if IS_PROD:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        # Never expose server token material (MutableHeaders has no .pop)
        try:
            del response.headers["X-Powered-By"]
        except KeyError:
            pass
        return response
