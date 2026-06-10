# -*- coding: utf-8 -*-
"""
modules/sync/sync.py

Команды:
- !sync        -> синхронизировать slash-команды на этом сервере (guild)
- !sync global -> синхронизировать глобально (может появляться не сразу)

Важно:
- Команда доступна только администраторам
- Сообщения на русском
"""

from __future__ import annotations

import discord
from discord.ext import commands


class SyncCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_cmd(self, ctx: commands.Context, scope: str = "guild"):
        """
        !sync guild  -> мгновенно на текущий сервер
        !sync global -> глобально (может долго обновляться)
        """
        scope = (scope or "guild").lower().strip()

        try:
            if scope in ("guild", "server", "сервер"):
                # КЛЮЧЕВО: переносим глобальные команды в guild, чтобы sync не вернул 0
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)

                await ctx.send(f"✅ Синхронизировано команд на сервере: **{len(synced)}**")
                return

            if scope in ("global", "all", "глобально"):
                synced = await self.bot.tree.sync()
                await ctx.send(
                    f"🌍 Глобально синхронизировано команд: **{len(synced)}**\n"
                    f"⚠️ Глобальные команды могут появляться не сразу."
                )
                return

            await ctx.send("❌ Используй: `!sync guild` или `!sync global`")

        except Exception as e:
            await ctx.send(f"❌ Ошибка синхронизации:\n```{e}```")

    @sync_cmd.error
    async def sync_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Недостаточно прав. Нужен администратор.")
        else:
            await ctx.send(f"❌ Ошибка:\n```{error}```")


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommands(bot))
