import discord
from typing import Optional
from .state import state

async def get_webhook(ch: discord.TextChannel) -> Optional[discord.Webhook]:
    """Get or create webhook for channel"""
    if ch.id in state.webhooks:
        return state.webhooks[ch.id]
    
    try:
        # Look for existing userphone webhook
        wh = next((w for w in await ch.webhooks() if w.name == "userphone"), None)
        if wh is None:
            wh = await ch.create_webhook(name="userphone")
        state.webhooks[ch.id] = wh
        return wh
    except discord.Forbidden:
        return None

async def remove_webhook(cid: int):
    """Remove webhook for channel"""
    wh = state.webhooks.pop(cid, None)
    if wh:
        try:
            await wh.delete()
        except Exception:
            pass

async def forward_message(content: str, files, alias: str, avatar: str, dest: discord.TextChannel):
    """Forward message to destination channel"""
    wh = await get_webhook(dest)
    if wh:
        m = await wh.send(
            content=content or None,
            username=alias,
            avatar_url=avatar,
            files=files or []
        )
    else:
        m = await dest.send(f"**{alias}**: {content}", files=files or [])
    return m