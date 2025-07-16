import random
import discord
from discord import app_commands
from discord.ext import commands

class Fun(commands.Cog):
    """Cog for fun commands and games"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question")
    async def eightball(self, interaction: discord.Interaction, question: str):
        """Magic 8-ball command"""
        responses = [
            "Yes", "No", "Maybe", "Ask again later", "Definitely", "Absolutely not",
            "It is certain", "Reply hazy, try again", "Don't count on it", "Yes definitely",
            "My sources say no", "Outlook not so good", "Better not tell you now"
        ]
        await interaction.response.send_message(f"🎱 {random.choice(responses)}")
    
    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        """Coin flip command"""
        result = "Heads" if random.random() < 0.5 else "Tails"
        await interaction.response.send_message(f"🪙 {result}")
    
    @app_commands.command(name="roll", description="Roll a dice")
    @app_commands.describe(sides="Number of sides (minimum 2)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        """Dice roll command"""
        sides = max(2, sides)
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 Rolled {result} out of {sides}")