"""Pluggable session store: in-memory fallback or Redis-backed.

The interface is intentionally tiny to keep the moving parts minimal.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, Optional

import structlog

logger = structlog.stdlib.get_logger()


class SessionData:
    """POJO holding per-session information."""

    def __init__(self, language: str, ttl: int, files: Optional[Dict[str, str]] = None):
        self.language = language
        self.ttl = ttl
        self.last_used = time.time()
        self.files: Dict[str, str] = files or {}

    # -------- serialisation helpers --------
    def dumps(self) -> str:
        return json.dumps(
            {
                "language": self.language,
                "ttl": self.ttl,
                "last_used": self.last_used,
                "files": self.files,
            }
        )

    @classmethod
    def loads(cls, payload: str) -> "SessionData":
        obj = json.loads(payload)
        inst = cls(obj["language"], obj["ttl"], obj["files"])
        inst.last_used = obj["last_used"]
        return inst

    # ---------------------------------------

    def touch(self):
        self.last_used = time.time()

    def expired(self) -> bool:
        return time.time() - self.last_used > self.ttl


# ---------------------------------------------------------------------------
# Store Base-class
# ---------------------------------------------------------------------------


class BaseSessionStore:
    async def create(self, sid: str, data: SessionData):
        raise NotImplementedError

    async def get(self, sid: str) -> Optional[SessionData]:
        raise NotImplementedError

    async def save(self, sid: str, data: SessionData):
        """Persist updated session (touch, files)."""
        raise NotImplementedError

    async def delete(self, sid: str):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------


class MemorySessionStore(BaseSessionStore):
    def __init__(self):
        self._store: Dict[str, SessionData] = {}

    async def create(self, sid: str, data: SessionData):
        self._store[sid] = data

    async def get(self, sid: str) -> Optional[SessionData]:
        data = self._store.get(sid)
        if data and data.expired():
            await self.delete(sid)
            return None
        return data

    async def save(self, sid: str, data: SessionData):
        self._store[sid] = data

    async def delete(self, sid: str):
        self._store.pop(sid, None)


# ---------------------------------------------------------------------------
# Redis-backed store
# ---------------------------------------------------------------------------


class RedisSessionStore(BaseSessionStore):
    def __init__(self, url: str):
        import redis.asyncio as redis  # lazy import

        self._r = redis.from_url(url, decode_responses=True)

    def _key(self, sid: str) -> str:  # namespacing helper
        return f"sf:session:{sid}"

    async def create(self, sid: str, data: SessionData):
        await self.save(sid, data)

    async def get(self, sid: str) -> Optional[SessionData]:
        payload = await self._r.get(self._key(sid))
        if payload is None:
            return None
        data = SessionData.loads(payload)
        if data.expired():
            await self.delete(sid)
            return None
        return data

    async def save(self, sid: str, data: SessionData):
        await self._r.set(self._key(sid), data.dumps(), ex=data.ttl)

    async def delete(self, sid: str):
        await self._r.delete(self._key(sid))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_store() -> BaseSessionStore:
    redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
    if redis_url:
        logger.info("Using Redis session store", url=redis_url)
        return RedisSessionStore(redis_url)
    logger.info("Using in-memory session store (development mode)")
    return MemorySessionStore()

