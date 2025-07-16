import os
import asyncio
from discord.ext import commands
import discord
from dotenv import load_dotenv

from cogs.pairing import Pairing
from cogs.relay import Relay
from cogs.fun import Fun
from cogs.admin import Admin

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Bot setup
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.reactions = True
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

@bot.event
async def on_ready():
    """Bot ready event"""
    print(f"🚀 {bot.user} is online!")
    print(f"📊 Serving {len(bot.guilds)} servers")
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

async def main():
    """Main bot setup and startup"""
    # Add cogs
    await bot.add_cog(Pairing(bot))
    await bot.add_cog(Relay(bot))
    await bot.add_cog(Fun(bot))
    await bot.add_cog(Admin(bot))
    
    # Start the bot
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())