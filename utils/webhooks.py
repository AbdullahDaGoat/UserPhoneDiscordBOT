# ──────────────────────────────────────────────
# utils/webhooks.py
# ──────────────────────────────────────────────
import discord
from typing import Optional
from .state import state

async def get_webhook(ch: discord.TextChannel) -> Optional[discord.Webhook]:
    if ch.id in state.webhooks:
        return state.webhooks[ch.id]
    try:
        wh = next((w for w in await ch.webhooks() if w.name == "userphone"), None)
        if wh is None:
            wh = await ch.create_webhook(name="userphone")
        state.webhooks[ch.id] = wh
        return wh
    except discord.Forbidden:
        return None

async def remove_webhook(cid: int):
    state.webhooks.pop(cid, None)

async def forward_message(content, files, alias, avatar, dest: discord.TextChannel):
    wh = await get_webhook(dest)
    if wh:
        return await wh.send(content=content or None,
                             username=alias,
                             avatar_url=avatar,
                             files=files or [])
    return await dest.send(f"**{alias}**: {content}", files=files or [])
