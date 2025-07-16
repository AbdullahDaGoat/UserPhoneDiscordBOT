import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.state import state

class Admin(commands.Cog):
    """Cog for administrative commands and monitoring"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Start auto-sync task when cog is loaded"""
        if not self.auto_sync.is_running():
            self.auto_sync.start()
    
    @app_commands.command(name="queue", description="Show current queue status")
    async def queue_status(self, interaction: discord.Interaction):
        """Show queue status"""
        regular_count = len(state.waiting_queue)
        anon_count = len(state.anon_queue)
        active_count = len(state.active_calls) // 2
        
        status = f"📊 **Queue Status**\n"
        status += f"Regular queue: {regular_count}\n"
        status += f"Anonymous queue: {anon_count}\n"
        status += f"Active calls: {active_count}"
        
        await interaction.response.send_message(status)
    
    @tasks.loop(minutes=30)
    async def auto_sync(self):
        """Auto-sync slash commands"""
        try:
            await self.bot.tree.sync()
            print("🔄 Auto-synced commands")
        except Exception as e:
            print(f"❌ Auto-sync failed: {e}")
    
    @auto_sync.before_loop
    async def before_auto_sync(self):
        """Wait for bot to be ready before auto-sync"""
        await self.bot.wait_until_ready()