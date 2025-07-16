import aiohttp
import io
import discord
from discord.ext import commands

from utils.state import state
from utils.webhooks import forward_message

class Relay(commands.Cog):
    """Cog for handling message forwarding between channels"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """Handle message forwarding"""
        if msg.author.bot or not isinstance(msg.channel, discord.TextChannel):
            return
        
        cid = msg.channel.id
        partner_id = state.active_calls.get(cid)
        if not partner_id:
            return
        
        # Rate limiting
        now = msg.created_at.timestamp()
        if now - state.last_sent.get(msg.author.id, 0) < state.COOLDOWN:
            return
        state.last_sent[msg.author.id] = now
        
        # Handle attachments
        files = [await a.to_file() for a in msg.attachments]
        
        # Handle stickers
        if msg.stickers:
            for st in msg.stickers:
                if st.format in (discord.StickerFormatType.png, discord.StickerFormatType.apng):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(st.url) as response:
                            data = io.BytesIO(await response.read())
                            files.append(discord.File(data, filename=f"{st.id}.png"))
        
        if not msg.content and not files:
            return
        
        partner = self.bot.get_channel(partner_id)
        if not partner:
            return
        
        # Get user info
        anon = state.is_anonymous(cid)
        alias = state.alias_for(msg.author, anon)
        avatar = state.avatar_for(msg.author, anon)
        
        # Check for profile changes (non-anon only)
        if not anon:
            lp_key = (msg.author.id, partner_id)
            prev = state.last_profile.get(lp_key, (None, None))
            if (alias, avatar) != prev:
                state.last_profile[lp_key] = (alias, avatar)
                if prev[0] is not None:  # Not first message
                    await partner.send(f"ℹ️ **{prev[0]}** updated their profile.")
        
        # Forward message
        dest_msg = await forward_message(msg.content, files, alias, avatar, partner)
        state.relay_map[(cid, msg.id)] = dest_msg.id
    
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Handle message edits"""
        src_ch = self.bot.get_channel(payload.channel_id)
        if not isinstance(src_ch, discord.TextChannel):
            return
        
        partner_id = state.active_calls.get(src_ch.id)
        if not partner_id:
            return
        
        dest_id = state.relay_map.get((src_ch.id, payload.message_id))
        if not dest_id:
            return
        
        partner_ch = self.bot.get_channel(partner_id)
        if not isinstance(partner_ch, discord.TextChannel):
            return
        
        content = payload.data.get("content", "")
        
        # Don't mirror if content becomes empty (embed-only edits)
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
        partner_id = state.active_calls.get(cid)
        if not partner_id:
            return
        
        partner_ch = self.bot.get_channel(partner_id)
        if not isinstance(partner_ch, discord.TextChannel):
            return
        
        # Get user info
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        member = guild.get_member(payload.user_id) if guild else None
        user = member or payload.member or payload.user
        
        if not user:
            return
        
        alias = state.alias_for(user, state.is_anonymous(cid))
        
        # Get message snippet
        try:
            src_ch = self.bot.get_channel(cid)
            src_msg = await src_ch.fetch_message(payload.message_id)
            snippet = (src_msg.content or "[non‑text]")[:60]
            if len(src_msg.content) > 60:
                snippet += "..."
        except Exception:
            snippet = "a message"
        
        await partner_ch.send(f"**{alias}** reacted with {payload.emoji} to \"{snippet}\"")