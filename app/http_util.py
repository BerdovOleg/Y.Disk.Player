from __future__ import annotations

"""Shared httpx helpers — prefer IPv4 to avoid macOS/Disk IPv6 route failures."""

from typing import Any

import httpx


def _ipv4_transport() -> httpx.AsyncHTTPTransport:
    # Bind local side to IPv4 so Dual-Stack does not pick a broken IPv6 path
    # ("LRC groups are unavailable in the local route table").
    return httpx.AsyncHTTPTransport(local_address="0.0.0.0")


def async_client(**kwargs: Any) -> httpx.AsyncClient:
    """httpx.AsyncClient that prefers IPv4."""
    kwargs.setdefault("transport", _ipv4_transport())
    return httpx.AsyncClient(**kwargs)


def is_network_io_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    needles = (
        "lrc groups",
        "file io failure",
        "network is unreachable",
        "nodename nor servname",
        "name or service not known",
        "connection reset",
        "timed out",
        "temporary failure",
    )
    return any(n in text for n in needles)
