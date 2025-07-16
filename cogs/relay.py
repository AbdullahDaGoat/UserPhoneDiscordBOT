# cogs/relay.py

import aiohttp
import io
import discord
from discord.ext import commands

from utils.state    import state
from utils.webhooks import forward_message

class Relay(commands.Cog):
    """Cog for handling message forwarding between channels"""
    
    def __init__(self, bot):
        self.bot = bot
        # For rate limiting (fallback when not using Redis)
        self.last_sent = {}
        # For tracking profile changes
        self.last_profile = {}
        # For message edit mapping
        self.relay_map = {}
    
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """Handle message forwarding"""
        if msg.author.bot or not isinstance(msg.channel, discord.TextChannel):
            return
        
        cid = msg.channel.id
        
        # Check if channel is in a call
        if not await state.is_in_call(cid):
            return
        
        # Get partner channel from active calls
        if state._r:
            partner_str = await state._r.hget(state._H_ACTIVE, str(cid))
            partner_id  = int(partner_str) if partner_str else None
        else:
            partner_id = state.active_calls.get(cid)
        
        if not partner_id:
            return
        
        # Rate limiting
        now = msg.created_at.timestamp()
        last = self.last_sent.get(msg.author.id, 0)
        if now - last < state.COOLDOWN:
            return
        self.last_sent[msg.author.id] = now
        
        # Handle attachments
        files = [await a.to_file() for a in msg.attachments]
        
        # Handle stickers, preserving GIF animation
        if msg.stickers:
            async with aiohttp.ClientSession() as session:
                for st in msg.stickers:
                    try:
                        async with session.get(st.url) as resp:
                            data = io.BytesIO(await resp.read())
                            # Choose extension based on sticker format
                            if st.format is discord.StickerFormatType.gif:
                                ext = "gif"
                            elif st.format is discord.StickerFormatType.apng:
                                ext = "png"
                            else:
                                ext = "png"
                            files.append(discord.File(data, filename=f"{st.id}.{ext}"))
                    except Exception:
                        continue
        
        if not msg.content and not files:
            return
        
        partner_ch = self.bot.get_channel(partner_id)
        if not partner_ch:
            return
        
        # Get user info
        anon   = await state.is_anonymous(cid)
        alias  = await state.alias_for(msg.author, anon)
        avatar = await state.avatar_for(msg.author, anon)
        
        # Check for profile changes (non-anon only)
        if not anon:
            lp_key = (msg.author.id, partner_id)
            prev = self.last_profile.get(lp_key, (None, None))
            if (alias, avatar) != prev:
                if prev[0] is not None:
                    await partner_ch.send(f"ℹ️ **{prev[0]}** updated their profile.")
                self.last_profile[lp_key] = (alias, avatar)
        
        # Forward message
        dest_msg = await forward_message(msg.content, files, alias, avatar, partner_ch)
        self.relay_map[(cid, msg.id)] = dest_msg.id
    
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Handle message edits"""
        src_ch = self.bot.get_channel(payload.channel_id)
        if not isinstance(src_ch, discord.TextChannel):
            return
        
        if not await state.is_in_call(src_ch.id):
            return
        
        # Get partner channel
        if state._r:
            partner_str = await state._r.hget(state._H_ACTIVE, str(src_ch.id))
            partner_id  = int(partner_str) if partner_str else None
        else:
            partner_id = state.active_calls.get(src_ch.id)
        
        if not partner_id:
            return
        
        dest_id = self.relay_map.get((src_ch.id, payload.message_id))
        if not dest_id:
            return
        
        partner_ch = self.bot.get_channel(partner_id)
        if not isinstance(partner_ch, discord.TextChannel):
            return
        
        content = payload.data.get("content", "")
        if content == "":
            return
        
        try:
            dest_msg = await partner_ch.fetch_message(dest_id)
            await dest_msg.edit(content=content)
        except Exception:
            pass
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction forwarding"""
        if payload.user_id == self.bot.user.id:
            return
        
        cid = payload.channel_id
        if not await state.is_in_call(cid):
            return
        
        # Get partner channel
        if state._r:
            partner_str = await state._r.hget(state._H_ACTIVE, str(cid))
            partner_id  = int(partner_str) if partner_str else None
        else:
            partner_id = state.active_calls.get(cid)
        
        if not partner_id:
            return
        
        partner_ch = self.bot.get_channel(partner_id)
        if not isinstance(partner_ch, discord.TextChannel):
            return
        
        guild  = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        member = guild.get_member(payload.user_id) if guild else None
        user   = member or payload.member or payload.user
        if not user:
            return
        
        alias = await state.alias_for(user, await state.is_anonymous(cid))
        
        # Get message snippet
        try:
            src_ch  = self.bot.get_channel(cid)
            src_msg = await src_ch.fetch_message(payload.message_id)
            snippet = (src_msg.content or "[non‑text]")[:60]
            if len(src_msg.content) > 60:
                snippet += "..."
        except Exception:
            snippet = "a message"
        
        await partner_ch.send(f"**{alias}** reacted with {payload.emoji} to \"{snippet}\"")

async def setup(bot: commands.Bot):
    await bot.add_cog(Relay(bot))
