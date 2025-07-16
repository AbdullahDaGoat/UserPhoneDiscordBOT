# ──────────────────────────────────────────────
# cogs/admin.py
# ──────────────────────────────────────────────
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.state import state

class Admin(commands.Cog):
    """Administrative commands and monitoring"""
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.auto_sync.is_running():
            self.auto_sync.start()

    @app_commands.command(name="queue", description="Show current queue status")
    async def queue_status(self, interaction: discord.Interaction):
        regular = len(state.waiting_queue)
        anon    = len(state.anon_queue)
        active  = await state.get_active_calls_count()
        msg = (f"📊 **Queue Status**\n"
               f"Regular queue: {regular}\n"
               f"Anonymous queue: {anon}\n"
               f"Active calls: {active}")
        await interaction.response.send_message(msg)

    @app_commands.command(name="stats", description="Show detailed userphone statistics")
    async def stats(self, interaction: discord.Interaction):
        regular = len(state.waiting_queue)
        anon    = len(state.anon_queue)
        active  = await state.get_active_calls_count()
        stats = (f"📈 **UserPhone Statistics**\n"
                 f"📞 Regular queue: {regular} waiting\n"
                 f"👤 Anonymous queue: {anon} waiting\n"
                 f"🔗 Active calls: {active}\n"
                 f"🌐 Total servers: {len(interaction.client.guilds)}")
        await interaction.response.send_message(stats)

    @tasks.loop(minutes=30)
    async def auto_sync(self):
        await self.bot.tree.sync()
        print("🔄 Slash‑commands auto‑synced")

    @auto_sync.before_loop
    async def before_auto_sync(self): await self.bot.wait_until_ready()

async def setup(bot): await bot.add_cog(Admin(bot))
