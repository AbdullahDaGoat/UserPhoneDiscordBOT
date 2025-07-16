# ──────────────────────────────────────────────
# utils/profiles.py
# ──────────────────────────────────────────────
from __future__ import annotations
import discord
from .state import state

async def alias_for(user: discord.abc.User, anonymous: bool = False) -> str:
    return await state.alias_for(user, anonymous)

async def avatar_for(user: discord.abc.User, anonymous: bool = False) -> str:
    return await state.avatar_for(user, anonymous)

async def set_profile(uid: int | str, alias: str | None, avatar_url: str | None) -> None:
    await state.set_profile(int(uid), alias, avatar_url)
