# utils/redis_pool.py

"""
Async‑friendly Redis client factory with DNS‑check and graceful fallback.

* Prefers REDIS_URL   (internal TLS URL on Railway)
* Falls back to REDIS_PUBLIC_URL for local testing
* Disables Redis if the host is unresolvable or the connection setup fails
* Returns None if Redis is disabled
"""
from __future__ import annotations
import os
import ssl
import socket
import urllib.parse

import redis.asyncio as aioredis

_RAW_URL: str | None = os.getenv("REDIS_URL") or os.getenv("REDIS_PUBLIC_URL")
_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """
    Return a singleton async Redis client, or None when:
      • no valid REDIS_URL is set
      • the hostname cannot be resolved
      • the connection setup fails
    """
    global _client

    # 1️⃣ No URL configured → disable Redis
    if not _RAW_URL or not _RAW_URL.startswith(("redis://", "rediss://", "unix://")):
        return None

    # 2️⃣ Already created → return it
    if _client is not None:
        return _client

    # 3️⃣ Parse URL and verify DNS
    parsed = urllib.parse.urlparse(_RAW_URL)
    host = parsed.hostname or ""
    port = parsed.port or (6380 if parsed.scheme == "rediss" else 6379)
    try:
        socket.getaddrinfo(host, port)
    except socket.gaierror as e:
        print(f"[Redis disabled] DNS lookup failed for {host}:{port} → {e}")
        return None

    # 4️⃣ Attempt to create the Redis client
    try:
        if parsed.scheme == "rediss":
            ssl_ctx = ssl.create_default_context()
            _client = aioredis.from_url(
                _RAW_URL,
                decode_responses=True,
                ssl=ssl_ctx,           # pass an SSLContext (compatible with all redis‑py versions)
            )
        else:
            _client = aioredis.from_url(
                _RAW_URL,
                decode_responses=True,
            )
        return _client

    except Exception as exc:
        print(f"[Redis disabled] Failed to initialize client → {exc}")
        _client = None
        return None
