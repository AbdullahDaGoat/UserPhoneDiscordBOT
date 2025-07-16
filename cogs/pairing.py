# cogs/pairing.py

import asyncio
import time
import traceback
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
        # maps user_id -> channel_id for queued callers
        self.user_queue: dict[int, int] = {}
        # maps channel_id -> placeholder message ID
        self.queue_msg: dict[int, int] = {}
        # per-guild rate-limit state
        self.guild_usage: dict[int, tuple[int,int]] = {}

    # ───────────────────── helpers ─────────────────────
    async def _edit(self, cid: int, text: str):
        """Edit the stored placeholder for channel `cid`."""
        mid = self.queue_msg.get(cid)
        if not mid:
            return
        ch = self.bot.get_channel(cid)
        try:
            msg = await ch.fetch_message(mid)
            await msg.edit(content=text)
        except Exception:
            pass
        # once connected or ended, drop the placeholder
        if text.startswith(("☎️", "📴", "❌")):
            self.queue_msg.pop(cid, None)

    async def _pair(self, ch1: discord.TextChannel, ch2: discord.TextChannel, anon: bool):
        """Wire two channels together and flip placeholders."""
        await state.start_call(ch1.id, ch2.id, anon)
        await self._edit(ch1.id, "☎️ Connected!")
        await self._edit(ch2.id, "☎️ Connected!")

    # ───────────────────── core handler ─────────────────────
    async def _handle_call(self, inter: discord.Interaction, anon: bool):
        ch, uid = inter.channel, inter.user.id

        # 0️⃣ only in text channels
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message(
                "Use this in a text channel.", ephemeral=True
            )

        # ▶️ Prevent two callers in the same channel
        if ch.id in self.user_queue.values() and self.user_queue.get(uid) != ch.id:
            return await inter.response.send_message(
                "This channel is already used by another caller. Please run `/call` in a different channel.",
                ephemeral=True,
            )

        # 1️⃣ ACK to avoid Discord timeouts
        await inter.response.defer(thinking=True)

        try:
            # 2️⃣ lightweight guards
            if await state.is_in_call(ch.id):
                return await inter.edit_original_response(
                    content="This channel is already in a live call."
                )
            if uid in self.user_queue and self.user_queue[uid] == ch.id:
                return await inter.edit_original_response(
                    content="You're already waiting here."
                )
            if uid in self.user_queue.values() and self.user_queue.get(uid) != ch.id:
                return await inter.edit_original_response(
                    content="You have another pending call elsewhere."
                )

            # per-server rate limit
            if inter.guild:
                gid = inter.guild.id
                used, reset = self.guild_usage.get(gid, (0, time.time() + self.SERVER_WINDOW))
                now = time.time()
                if now > reset:
                    used, reset = 0, now + self.SERVER_WINDOW
                if used >= self.SERVER_LIMIT:
                    return await inter.edit_original_response(
                        content=f"🚦 This server hit the {self.SERVER_LIMIT}/h limit."
                    )
                self.guild_usage[gid] = (used + 1, reset)

            # 3️⃣ queue bookkeeping
            # mark this user as queued on this channel
            self.user_queue[uid] = ch.id
            queue = state.anon_queue if anon else state.waiting_queue

            # attempt to find a partner from a different guild
            partner_cid: Optional[int] = None
            for _ in range(len(queue)):
                candidate = queue[0]
                owner = next((u for u, cid in self.user_queue.items() if cid == candidate), None)
                candidate_ch = self.bot.get_channel(candidate)
                if owner and owner != uid and candidate_ch and candidate_ch.guild.id != ch.guild.id:
                    partner_cid = queue.popleft()
                    break
                queue.rotate(-1)

            # instant match
            if partner_cid:
                msg = await inter.edit_original_response(content="🔗 Connecting…")
                self.queue_msg[ch.id] = msg.id
                partner_ch = self.bot.get_channel(partner_cid)
                await self._pair(ch, partner_ch, anon)
                return

            # else, enqueue
            queue.append(ch.id)
            pos = len(queue)
            msg = await inter.edit_original_response(
                content=f"📞 Calling… you're **#{pos}** in line."
            )
            self.queue_msg[ch.id] = msg.id

        except Exception:
            traceback.print_exc()
            await inter.edit_original_response(
                content="⚠️ Unexpected error – please try again shortly."
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

        # 1️⃣ live call?
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

        # 2️⃣ queued?
        queued_cid = self.user_queue.pop(uid, None)
        if queued_cid:
            for q in (state.waiting_queue, state.anon_queue):
                if queued_cid in q:
                    q.remove(queued_cid)
            await self._edit(queued_cid, "❌ Cancelled.")
            return await inter.edit_original_response(content="Left queue.")

        await inter.edit_original_response(content="You're not in a call or queue.")

    # ───── misc ─────
    @app_commands.command(name="duration", description="Show current call duration")
    async def duration(self, inter: discord.Interaction):
        ch = inter.channel
        if not isinstance(ch, discord.TextChannel):
            return await inter.response.send_message("Use in text channel.", ephemeral=True)
        mins = await state.get_call_duration(ch.id)
        if mins is None:
            return await inter.response.send_message("This channel isn't in a call.", ephemeral=True)
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
