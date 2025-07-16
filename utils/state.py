# ──────────────────────────────────────────────
# utils/state.py
# ──────────────────────────────────────────────
from __future__ import annotations
import time, json, pathlib
from collections import deque
from typing import Dict, Optional
import discord

from .redis_pool import get_redis

waiting_queue: deque[int] = deque()
anon_queue:    deque[int] = deque()

class State:
    COOLDOWN     = 1
    DEFAULT_AV   = "https://i.imgur.com/0h6wYht.png"

    waiting_queue = waiting_queue
    anon_queue    = anon_queue

    _H_ACTIVE  = "up:active"      # ch_id -> partner_id
    _H_STARTED = "up:started"     # ch_id -> unix ts
    _S_ANON    = "up:anon"        # set of channel_ids
    _P_PROFILE = "up:profile:"    # prefix for user hash

    def __init__(self):
        self._r = get_redis()

        # JSON‑fallback stores
        self.active_calls: Dict[int, int]   = {}
        self.call_started: Dict[int, float] = {}
        self.anon_channels: set[int]        = set()
        self.webhooks: Dict[int, discord.Webhook] = {}

        self._json_path = pathlib.Path(__file__).with_name("user_settings.json")
        if self._r is None:
            try:
                self.user_settings: Dict[str, dict] = json.loads(self._json_path.read_text())
            except FileNotFoundError:
                self.user_settings = {}

    # ───────── profile key helper ─────────
    def _profile(self, uid: int | str) -> str:
        return f"{self._P_PROFILE}{uid}"

    # ───────── call control ─────────
    async def start_call(self, c1: int, c2: int, anon: bool):
        if self._r:
            await self._r.hset(
                self._H_ACTIVE,
                mapping={str(c1): str(c2), str(c2): str(c1)}
            )
            now = int(time.time())
            await self._r.hset(
                self._H_STARTED,
                mapping={str(c1): now, str(c2): now}
            )
            if anon:
                await self._r.sadd(self._S_ANON, str(c1), str(c2))
            return

        self.active_calls[c1] = c2
        self.active_calls[c2] = c1
        now = time.time()
        self.call_started[c1] = self.call_started[c2] = now
        if anon:
            self.anon_channels.update({c1, c2})

    async def end_call(self, cid: int) -> Optional[int]:
        if self._r:
            partner = await self._r.hget(self._H_ACTIVE, str(cid))
            if partner:
                await self._r.hdel(self._H_ACTIVE, str(cid), partner)
                await self._r.hdel(self._H_STARTED, str(cid), partner)
                await self._r.srem(self._S_ANON, str(cid), partner)
                return int(partner)
            return None

        partner = self.active_calls.pop(cid, None)
        if partner:
            self.active_calls.pop(partner, None)
            self.call_started.pop(cid, None)
            self.call_started.pop(partner, None)
            self.anon_channels.discard(cid)
            self.anon_channels.discard(partner)
        return partner

    async def is_in_call(self, cid: int) -> bool:
        if self._r:
            return await self._r.hexists(self._H_ACTIVE, str(cid))
        return cid in self.active_calls

    async def get_call_duration(self, cid: int) -> Optional[int]:
        if self._r:
            ts = await self._r.hget(self._H_STARTED, str(cid))
            return int((time.time() - int(ts)) // 60) if ts else None
        start = self.call_started.get(cid)
        return int((time.time() - start) // 60) if start else None

    async def is_anonymous(self, cid: int) -> bool:
        if self._r:
            return await self._r.sismember(self._S_ANON, str(cid))
        return cid in self.anon_channels

    async def get_active_calls_count(self) -> int:
        if self._r:
            return (await self._r.hlen(self._H_ACTIVE)) // 2
        return len(self.active_calls) // 2

    async def get_all_active_calls(self) -> Dict[int, int]:
        if self._r:
            calls = await self._r.hgetall(self._H_ACTIVE)
            return {int(k): int(v) for k, v in calls.items()}
        return self.active_calls.copy()

    # ───────── profile helpers ─────────
    async def alias_for(self, user: discord.User, anon: bool) -> str:
        if anon:
            return f"Stranger {str(user.id)[-4:]}"
        if self._r:
            a = await self._r.hget(self._profile(user.id), "alias")
            return a or user.display_name
        return self.user_settings.get(str(user.id), {}).get("alias", user.display_name)

    async def avatar_for(self, user: discord.User, anon: bool) -> str:
        if anon:
            return self.DEFAULT_AV
        if self._r:
            url = await self._r.hget(self._profile(user.id), "avatar_url")
            return url or user.display_avatar.url
        return self.user_settings.get(str(user.id), {}).get("avatar_url", user.display_avatar.url)

    async def set_profile(self, uid: int, alias: str | None, avatar_url: str | None):
        if self._r:
            key = self._profile(uid)
            if alias is not None:
                await self._r.hset(key, "alias", alias.strip()[:32])
            if avatar_url is not None:
                await self._r.hset(key, "avatar_url", avatar_url.strip())
            return

        data = self.user_settings.get(str(uid), {})
        if alias is not None:
            data["alias"] = alias.strip()[:32]
        if avatar_url is not None:
            data["avatar_url"] = avatar_url.strip()
        self.user_settings[str(uid)] = data
        self._json_path.write_text(json.dumps(self.user_settings, indent=2))

state = State()
