# cogs/pairing.py  –  drop‑in replacement
import asyncio, time, traceback
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.state     import state
from utils.profiles  import set_profile
from utils.webhooks  import remove_webhook


class Pairing(commands.Cog):
    """UserPhone: /call · /anoncall · /hangup · /duration · /settings"""

    SERVER_LIMIT  = 50          # calls per guild per hour
    SERVER_WINDOW = 60 * 60     # window length (s)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_queue: dict[int, int] = {}        # user_id  -> channel_id
        self.queue_msg:  dict[int, int] = {}        # channel_id -> placeholder id
        self.guild_usage: dict[int, tuple[int,int]] = {}  # guild_id -> (count, reset_ts)

    # ───────────────────── helpers ─────────────────────
    async def _edit(self, cid: int, text: str):
        """Edit stored placeholder for channel `cid`."""
        mid = self.queue_msg.get(cid)
        if not mid:
            return
        ch = self.bot.get_channel(cid)
        try:
            m = await ch.fetch_message(mid)
            await m.edit(content=text)
        except Exception:
            pass
        if text.startswith(("☎️", "📴", "❌")):
            self.queue_msg.pop(cid, None)

    async def _pair(self, ch1: discord.TextChannel, ch2: discord.TextChannel, anon: bool):
        await state.start_call(ch1.id, ch2.id, anon)
        await self._edit(ch1.id, "☎️ Connected!")
        await self._edit(ch2.id, "☎️ Connected!")

    # ───────────────────── core handler ─────────────────────
    async def _handle_call(self, inter: discord.Interaction, anon: bool):
        ch  = inter.channel
        uid = inter.user.id

        # 0️⃣ channel type check *before* we defer
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use this in a text channel.", ephemeral=True)

        # 1️⃣ ACK – from now on Discord will never time‑out
        await inter.response.defer(thinking=True)   # non‑ephemeral placeholder

        try:
            # 2️⃣ lightweight guards ───────────────────────────
            if await state.is_in_call(ch.id):
                return await inter.edit_original_response(content="This channel is already in a call.")

            if uid in self.user_queue:
                return await inter.edit_original_response(content="You're already queued elsewhere.")

            # per‑guild quota
            if inter.guild:
                gid   = inter.guild.id
                used, reset = self.guild_usage.get(gid, (0, time.time()+self.SERVER_WINDOW))
                now = time.time()
                if now > reset:
                    used, reset = 0, now + self.SERVER_WINDOW
                if used >= self.SERVER_LIMIT:
                    return await inter.edit_original_response(
                        content=f"🚦 This server hit the {self.SERVER_LIMIT}/h call limit."
                    )
                self.guild_usage[gid] = (used+1, reset)

            # 3️⃣ matching / queue bookkeeping ─────────────────
            self.user_queue[uid] = ch.id
            queue = state.anon_queue if anon else state.waiting_queue

            # look for partner
            partner_cid = None
            for _ in range(len(queue)):
                candidate = queue[0]
                owner_uid = next((u for u,cid in self.user_queue.items() if cid == candidate), None)
                if owner_uid and owner_uid != uid:
                    partner_cid = queue.popleft()
                    break
                queue.rotate(-1)

            # instant match?
            if partner_cid:
                msg = await inter.edit_original_response(content="🔗 Connecting…")
                self.queue_msg[ch.id] = msg.id
                partner_ch = self.bot.get_channel(partner_cid)
                await self._pair(ch, partner_ch, anon)
                return

            # else enqueue
            queue.append(ch.id)
            pos  = len(queue)
            msg  = await inter.edit_original_response(
                content=f"📞 Calling… you're **#{pos}** in line."
            )
            self.queue_msg[ch.id] = msg.id

        except Exception:
            traceback.print_exc()
            await inter.edit_original_response(
                content="⚠️ Unexpected error – try again in a moment."
            )

    # ───────────────────── slash commands ─────────────────────
    @app_commands.command(name="call", description="Connect this channel to another")
    async def call(self, inter: discord.Interaction):
        await self._handle_call(inter, anon=False)

    @app_commands.command(name="anoncall", description="Anonymous call (hides profile)")
    async def anoncall(self, inter: discord.Interaction):
        await self._handle_call(inter, anon=True)

    @app_commands.command(name="hangup", description="End current call or leave queue")
    async def hangup(self, inter: discord.Interaction):
        ch, uid = inter.channel, inter.user.id
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in text channel.", ephemeral=True)

        await inter.response.defer(ephemeral=True)

        # 1) live call?
        partner_id = await state.end_call(ch.id)
        if partner_id:
            await self._edit(ch.id,      "📴 Ended.")
            await self._edit(partner_id, "📴 Call ended by other side.")
            partner_ch = self.bot.get_channel(partner_id)
            if partner_ch:
                await partner_ch.send("📴 Call ended by the other side.")
            await asyncio.gather(
                remove_webhook(ch.id), remove_webhook(partner_id),
                return_exceptions=True
            )
            return await inter.edit_original_response(content="Call ended.")

        # 2) queued?
        queued_cid = self.user_queue.pop(uid, None)
        if queued_cid:
            for q in (state.waiting_queue, state.anon_queue):
                if queued_cid in q:
                    q.remove(queued_cid)
            await self._edit(queued_cid, "❌ Cancelled.")
            return await inter.edit_original_response(content="Left queue.")

        await inter.edit_original_response(content="You're not in a call or queue.")

    # —— misc —— 
    @app_commands.command(name="duration", description="Show current call duration")
    async def duration(self, inter: discord.Interaction):
        ch = inter.channel
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in text channel.", ephemeral=True)
        mins = await state.get_call_duration(ch.id)
        if mins is None:
            return await inter.response.send_message(
                "This channel isn't in a call.", ephemeral=True
            )
        await inter.response.send_message(f"⏱️ {mins} minute(s) connected.", ephemeral=True)

    @app_commands.command(name="settings", description="Set alias / avatar")
    @app_commands.describe(alias="Display name", avatar_url="Avatar image URL")
    async def settings(self, inter: discord.Interaction,
                       alias: Optional[str] = None,
                       avatar_url: Optional[str] = None):
        await set_profile(inter.user.id, alias, avatar_url)
        await inter.response.send_message("⚙️ Settings saved.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pairing(bot))
