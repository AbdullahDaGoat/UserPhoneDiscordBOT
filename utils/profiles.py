"""
User‑profile helpers: alias + custom avatar storage.

All data lives in `user_settings.json` next to the bot.
"""
from __future__ import annotations
import json, os, pathlib
import discord

# file next to project root
SETTINGS_PATH = pathlib.Path(__file__).with_name("user_settings.json")
DEFAULT_AVATAR = "https://i.imgur.com/0h6wYht.png"   # generic anon picture

# load (or start fresh)
try:
    USER_SETTINGS: dict[str, dict] = json.loads(SETTINGS_PATH.read_text())
except FileNotFoundError:
    USER_SETTINGS = {}


# ── convenience wrappers ─────────────────────────────────────────────
def flush() -> None:
    SETTINGS_PATH.write_text(json.dumps(USER_SETTINGS, indent=2))


def alias_for(user: discord.abc.User, anonymous: bool = False) -> str:
    if anonymous:
        return f"Stranger {str(user.id)[-4:]}"
    return USER_SETTINGS.get(str(user.id), {}).get("alias", user.display_name)


def avatar_for(user: discord.abc.User, anonymous: bool = False) -> str:
    if anonymous:
        return DEFAULT_AVATAR
    return USER_SETTINGS.get(str(user.id), {}).get(
        "avatar_url",  user.display_avatar.url
    )


def set_profile(uid: int | str, alias: str | None, avatar_url: str | None) -> None:
    uid = str(uid)
    data = USER_SETTINGS.get(uid, {})
    if alias is not None:
        data["alias"] = alias.strip()[:32]
    if avatar_url is not None:
        data["avatar_url"] = avatar_url.strip()
    USER_SETTINGS[uid] = data
    flush()
