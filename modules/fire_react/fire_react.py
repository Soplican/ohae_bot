import discord
from discord.ext import commands

class FireReact(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.target_user_id = 609755494411796511  # ID пользователя

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Не реагируем на свои сообщения
        if message.author.id == self.bot.user.id:
            return
        # Если автор - нужный пользователь
        if message.author.id == self.target_user_id:
            try:
                # Добавляем реакцию 🔥💩🤘
                await message.add_reaction("🦄")
            except discord.Forbidden:
                # Нет прав на добавление реакций в этом канале
                pass
            except discord.HTTPException:
                # Ошибка при добавлении реакции (например, эмодзи не найден)
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(FireReact(bot))