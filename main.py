# ──────────────────────────────────────────────
# main.py  ─ entrypoint
# ──────────────────────────────────────────────
import os, asyncio, discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.pairing import Pairing
from cogs.relay   import Relay
from cogs.fun     import Fun
from cogs.admin   import Admin

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

INTENTS               = discord.Intents.default()
INTENTS.message_content = True
INTENTS.reactions       = True
INTENTS.members         = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

@bot.event
async def on_ready():
    print(f"🚀 {bot.user} is online!")
    print(f"📊 Serving {len(bot.guilds)} servers")
    synced = await bot.tree.sync()
    print(f"✅ Synced {len(synced)} command(s)")

async def main():
    await bot.add_cog(Pairing(bot))
    await bot.add_cog(Relay(bot))
    await bot.add_cog(Fun(bot))
    await bot.add_cog(Admin(bot))
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
