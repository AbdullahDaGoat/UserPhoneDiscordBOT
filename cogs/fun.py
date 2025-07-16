# ──────────────────────────────────────────────
# cogs/fun.py
# ──────────────────────────────────────────────
import random, discord
from discord import app_commands
from discord.ext import commands

class Fun(commands.Cog):
    """Simple fun commands"""

    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8‑ball a question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = [
            "Yes", "No", "Maybe", "Ask again later", "Definitely", "Absolutely not",
            "It is certain", "Reply hazy, try again", "Don't count on it", "Yes definitely",
            "My sources say no", "Outlook not so good", "Better not tell you now"
        ]
        await interaction.response.send_message(f"🎱 {random.choice(responses)}")

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 {'Heads' if random.random() < 0.5 else 'Tails'}")

    @app_commands.command(name="roll", description="Roll a dice")
    @app_commands.describe(sides="Number of sides (minimum 2)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        sides  = max(2, sides)
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 Rolled {result} out of {sides}")

async def setup(bot): await bot.add_cog(Fun(bot))
