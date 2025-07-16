# cogs/pairing.py
import asyncio, time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.state import state
from utils.profiles import alias_for, set_profile
from utils.webhooks import remove_webhook


class Pairing(commands.Cog):
    """
    /call  /anoncall  /hangup  /duration  /settings
    Queues users, prevents self‑match, edits “Calling…” → “Connected!”.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_queue: dict[int, int] = {}      # user_id  → channel_id
        self.queue_msg: dict[int, int] = {}       # channel_id → message_id

    # ────────────────── helpers ──────────────────
    async def _edit_queue_msg(self, cid: int, new_text: str):
        msg_id = self.queue_msg.get(cid)
        if not msg_id:
            return
        ch = self.bot.get_channel(cid)
        try:
            m = await ch.fetch_message(msg_id)
            await m.edit(content=new_text)
        except Exception:
            pass
        finally:
            self.queue_msg.pop(cid, None)

    async def _pair(self, ch1: discord.TextChannel, ch2: discord.TextChannel, anon: bool):
        """Connect two channels and flip their queue messages to Connected."""
        state.start_call(ch1.id, ch2.id, anon)
        await self._edit_queue_msg(ch1.id, "☎️ Connected!")
        await self._edit_queue_msg(ch2.id, "☎️ Connected!")
        await ch1.send("☎️ Connected!")
        await ch2.send("☎️ Connected!")

    async def _enqueue(self,
                       interaction: discord.Interaction,
                       ch: discord.TextChannel,
                       queue: list[int]):
        queue.append(ch.id)
        pos = len(queue)
        msg = await interaction.channel.send(f"📞 Calling… you're **#{pos}** in line.")
        self.queue_msg[ch.id] = msg.id

    def _find_partner(self, queue: list[int], requester_uid: int) -> Optional[int]:
        """
        Return first channel in queue not owned by requester.
        Rotate queue to preserve order.
        """
        for _ in range(len(queue)):
            cid = queue[0]
            owner_uid = next((u for u, cc in self.user_queue.items() if cc == cid), None)
            if owner_uid and owner_uid != requester_uid:
                return queue.popleft()
            queue.rotate(-1)        # move to end and keep searching
        return None

    # ────────────────── commands ──────────────────
    @app_commands.command(name="call", description="Connect this channel to another")
    async def call(self, inter: discord.Interaction):
        await self._handle_call(inter, anon=False)

    @app_commands.command(name="anoncall", description="Anonymous call (hides profile)")
    async def anoncall(self, inter: discord.Interaction):
        await self._handle_call(inter, anon=True)

    async def _handle_call(self, inter: discord.Interaction, anon: bool):
        ch = inter.channel
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in a text channel.", ephemeral=True)

        uid = inter.user.id
        if state.is_in_call(ch.id):
            return await inter.response.send_message("Channel already in a call.", ephemeral=True)
        if uid in self.user_queue:
            return await inter.response.send_message("You’re already queued.", ephemeral=True)

        # record this user→channel BEFORE matching so the partner sees it
        self.user_queue[uid] = ch.id

        queue = state.anon_queue if anon else state.waiting_queue
        partner_cid = self._find_partner(queue, uid)

        if partner_cid:
            # create visible “Connecting…” msg in this channel
            msg = await ch.send("🔗 Connecting…")
            self.queue_msg[ch.id] = msg.id

            await inter.response.defer()  # no ephemeral bubble
            partner_ch = self.bot.get_channel(partner_cid)
            await self._pair(ch, partner_ch, anon)
            return

        # no partner yet ➜ enqueue
        await self._enqueue(inter, ch, queue)
        await inter.response.defer()

    @app_commands.command(name="hangup", description="End current call or leave queue")
    async def hangup(self, inter: discord.Interaction):
        ch = inter.channel
        uid = inter.user.id
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in a text channel.", ephemeral=True)

        # if channel is active → end it
        partner_id = state.end_call(ch.id)
        if partner_id:
            await ch.send("📴 Call ended.")
            partner = self.bot.get_channel(partner_id)
            if partner:
                await partner.send("📴 Call ended by the other side.")
            await asyncio.gather(remove_webhook(ch.id),
                                 remove_webhook(partner_id),
                                 return_exceptions=True)
            return await inter.response.send_message("Call ended.", ephemeral=True)

        # if user queued elsewhere → remove
        queued_cid = self.user_queue.pop(uid, None)
        if queued_cid:
            for q in (state.waiting_queue, state.anon_queue):
                if queued_cid in q:
                    q.remove(queued_cid)
            await self._edit_queue_msg(queued_cid, "❌ Cancelled.")
            return await inter.response.send_message("Left queue.", ephemeral=True)

        await inter.response.send_message("Not in call or queue.", ephemeral=True)

    @app_commands.command(name="duration", description="Show current call duration")
    async def duration(self, inter: discord.Interaction):
        ch = inter.channel
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in text channel.", ephemeral=True)
        mins = state.get_call_duration(ch.id)
        if mins is None:
            return await inter.response.send_message("Channel not in a call.", ephemeral=True)
        await inter.response.send_message(f"⏱️ {mins} minute(s) connected.", ephemeral=True)

    @app_commands.command(name="settings", description="Set alias / avatar")
    @app_commands.describe(alias="Display name", avatar_url="Avatar image URL")
    async def settings(self, inter: discord.Interaction,
                       alias: Optional[str] = None,
                       avatar_url: Optional[str] = None):
        set_profile(inter.user.id, alias, avatar_url)
        await inter.response.send_message("⚙️ Settings saved.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pairing(bot))
