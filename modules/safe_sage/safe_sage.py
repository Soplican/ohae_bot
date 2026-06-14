import discord
from discord.ext import commands

TARGET_USER_ID = 906060308450263092

class SafeSage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if (
            message.author.id == TARGET_USER_ID
            and "пидорас" in message.content.lower()
        ):
            await message.channel.send("мама твоя")

async def setup(bot):
    await bot.add_cog(SafeSage(bot))