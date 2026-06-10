import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import traceback
import logging

logger = logging.getLogger(__name__)

class logging_system(commands.Cog):
    """Система логирования всех событий (только для указанного сервера)"""

    def __init__(self, bot):
        self.bot = bot
        self.allowed_guild_id = 1514058295579643984  # ID вашего сервера
        self.log_channels = {
            "voice": 1514062889659400212,      # 🔊・voice-join-leave
            "roles": 1514062918537314434,      # 🔮・role-changes-logs
            "name": 1514062945502494800,       # 📑・log-name-edit
            "messages": 1514062973788749955,   # 📩・message-logs
            "join_leave": 1514063002079592608, # 📊・join-leave-user
            "mod": 1514063039689658559,        # ⛔・ban-kick-user
            "other": 1514063067057623211       # 📦・other-logs
        }

    def is_allowed_guild(self, guild_id: int) -> bool:
        return guild_id == self.allowed_guild_id

    def get_channel(self, channel_name: str, guild_id: int = None):
        """Получает канал, если сервер разрешён, иначе None"""
        if guild_id and not self.is_allowed_guild(guild_id):
            return None
        channel_id = self.log_channels.get(channel_name)
        if not channel_id:
            logger.warning(f"Неизвестный канал: {channel_name}")
            return None
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"Канал {channel_name} (ID: {channel_id}) не найден")
        return channel

    async def safe_send(self, channel, embed, event_name=""):
        """Безопасная отправка с обработкой ошибок"""
        if not channel:
            logger.warning(f"{event_name}: канал отсутствует, пропускаю")
            return
        try:
            await channel.send(embed=embed)
            logger.info(f"{event_name}: лог отправлен в #{channel.name}")
        except discord.Forbidden:
            logger.error(f"{event_name}: нет прав на отправку в {channel.mention}")
        except discord.HTTPException as e:
            logger.error(f"{event_name}: ошибка Discord: {e}")
        except Exception:
            logger.error(f"{event_name}: неожиданная ошибка:\n{traceback.format_exc()}")

    def create_embed(self, title: str, description: str, color: int, fields: list = None, thumbnail: str = None):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        embed.set_footer(text=f"• {datetime.now().strftime('%H:%M:%S')}")
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        return embed

    # ---------- УНИВЕРСАЛЬНЫЙ ПОИСК В АУДИТ-ЛОГЕ ----------
    async def find_audit_log_entry(self, guild, action, target_id=None, limit=50):
        """Ищет запись аудит-лога по действию и, если указан, по ID цели."""
        if not guild.me.guild_permissions.view_audit_log:
            logger.warning(f"Нет прав на просмотр аудит-лога в {guild.name}")
            return None
        try:
            async for entry in guild.audit_logs(limit=limit, action=action):
                if target_id is None or (entry.target and entry.target.id == target_id):
                    return entry
        except Exception as e:
            logger.error(f"Ошибка получения аудит-лога: {e}")
        return None

    # ---------- ГОЛОСОВЫЕ ЛОГИ ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.is_allowed_guild(member.guild.id):
            return
        channel = self.get_channel("voice", member.guild.id)
        if not channel:
            return

        action = None
        fields = []
        color = 0x57F287

        if before.channel is None and after.channel is not None:
            action = "join"
            title = "🔊 ГОЛОСОВОЙ ЗАХОД"
            color = 0x57F287
            fields.append(("📌 Канал", after.channel.mention, True))
        elif before.channel is not None and after.channel is None:
            action = "leave"
            title = "🔊 ГОЛОСОВОЙ ВЫХОД"
            color = 0xED4245
            fields.append(("📌 Канал", before.channel.mention, True))
        elif before.channel != after.channel:
            action = "move"
            title = "🔄 ГОЛОСОВОЕ ПЕРЕМЕЩЕНИЕ"
            color = 0xFEE75C
            fields.extend([
                ("⬅️ Откуда", before.channel.mention, True),
                ("➡️ Куда", after.channel.mention, True)
            ])

        voice_changes = []
        if before.self_mute != after.self_mute:
            voice_changes.append(f"🔇 Само-мут: {'вкл' if after.self_mute else 'выкл'}")
        if before.self_deaf != after.self_deaf:
            voice_changes.append(f"🔇 Само-оглушение: {'вкл' if after.self_deaf else 'выкл'}")
        if before.mute != after.mute:
            voice_changes.append(f"🎤 Серверный мут: {'вкл' if after.mute else 'выкл'}")
        if before.deaf != after.deaf:
            voice_changes.append(f"🎧 Серверное оглушение: {'вкл' if after.deaf else 'выкл'}")
        if before.self_video != after.self_video:
            voice_changes.append(f"📹 Видео: {'вкл' if after.self_video else 'выкл'}")
        if before.self_stream != after.self_stream:
            voice_changes.append(f"📡 Стрим: {'вкл' if after.self_stream else 'выкл'}")

        if voice_changes and action is None:
            action = "state"
            title = "🎤 ИЗМЕНЕНИЕ СОСТОЯНИЯ В ГОЛОСЕ"
            color = 0x5865F2
            fields = [("📌 Канал", after.channel.mention if after.channel else before.channel.mention, True)]
        elif voice_changes:
            fields.append(("📊 Изменения", "\n".join(voice_changes), False))

        if action:
            embed = self.create_embed(
                title=f"**{title}**",
                description=f"{member.mention}",
                color=color,
                fields=fields + [
                    ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                    ("🕵️ Инициатор", member.mention, True),
                    ("⏰ Время", f"<t:{int(datetime.now().timestamp())}:R>", True)
                ],
                thumbnail=member.display_avatar.url
            )
            await self.safe_send(channel, embed, f"voice_{action}")

        # ---------- ЛОГИ СТРИМОВ ----------
        if not before.self_stream and after.self_stream:
            embed = self.create_embed(
                title="📡 **СТРИМ НАЧАЛСЯ**",
                description=f"{member.mention} начал стрим",
                color=0x57F287,
                fields=[
                    ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                    ("📌 Канал", after.channel.mention, True)
                ],
                thumbnail=member.display_avatar.url
            )
            await self.safe_send(channel, embed, "stream_start")

        if before.self_stream and not after.self_stream:
            embed = self.create_embed(
                title="📡 **СТРИМ ЗАКОНЧИЛСЯ**",
                description=f"{member.mention} завершил стрим",
                color=0xED4245,
                fields=[
                    ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                    ("📌 Канал", before.channel.mention, True)
                ],
                thumbnail=member.display_avatar.url
            )
            await self.safe_send(channel, embed, "stream_end")

    # ---------- ЛОГИ РОЛЕЙ ----------
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if not self.is_allowed_guild(after.guild.id):
            return

        # Изменение ролей
        if before.roles != after.roles:
            channel = self.get_channel("roles", after.guild.id)
            if not channel:
                return

            added = [r for r in after.roles if r not in before.roles]
            removed = [r for r in before.roles if r not in after.roles]

            entry = await self.find_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, target_id=after.id)
            moderator = entry.user if entry else None

            for role in added:
                embed = self.create_embed(
                    title="➕ **РОЛЬ ДОБАВЛЕНА**",
                    description=f"{after.mention} получил роль",
                    color=0x57F287,
                    fields=[
                        ("🎭 Роль", f"{role.mention} | `{role.id}`", True),
                        ("👤 Участник", f"{after.mention} | `{after.id}`", True),
                        ("🛡️ Изменил", moderator.mention if moderator else "`Неизвестно`", True),
                        ("⏰ Время", f"<t:{int(datetime.now().timestamp())}:R>", True)
                    ],
                    thumbnail=after.display_avatar.url
                )
                await self.safe_send(channel, embed, "role_add")
                await asyncio.sleep(0.5)

            for role in removed:
                embed = self.create_embed(
                    title="➖ **РОЛЬ УДАЛЕНА**",
                    description=f"{after.mention} лишился роли",
                    color=0xED4245,
                    fields=[
                        ("🎭 Роль", f"{role.mention} | `{role.id}`", True),
                        ("👤 Участник", f"{after.mention} | `{after.id}`", True),
                        ("🛡️ Изменил", moderator.mention if moderator else "`Неизвестно`", True),
                        ("⏰ Время", f"<t:{int(datetime.now().timestamp())}:R>", True)
                    ],
                    thumbnail=after.display_avatar.url
                )
                await self.safe_send(channel, embed, "role_remove")
                await asyncio.sleep(0.5)

        # Изменение ника
        if before.nick != after.nick:
            channel = self.get_channel("name", after.guild.id)
            if not channel:
                return

            entry = await self.find_audit_log_entry(after.guild, discord.AuditLogAction.member_update, target_id=after.id)
            moderator = entry.user if entry else after

            if before.nick is None:
                title, color, desc = "📝 НИК УСТАНОВЛЕН", 0x57F287, f"{after.mention} установил ник"
                fields = [("🆕 Новый ник", f"`{after.nick}`", True)]
            elif after.nick is None:
                title, color, desc = "📝 НИК УДАЛЕН", 0xED4245, f"{after.mention} удалил ник"
                fields = [("🗑️ Старый ник", f"`{before.nick}`", True)]
            else:
                title, color, desc = "📝 НИК ИЗМЕНЕН", 0xFEE75C, f"{after.mention} изменил ник"
                fields = [("⬅️ Было", f"`{before.nick}`", True), ("➡️ Стало", f"`{after.nick}`", True)]

            embed = self.create_embed(
                title=f"**{title}**",
                description=desc,
                color=color,
                fields=fields + [
                    ("👤 Участник", f"{after.mention} | `{after.id}`", True),
                    ("🛡️ Изменил", moderator.mention, True)
                ],
                thumbnail=after.display_avatar.url
            )
            await self.safe_send(channel, embed, "nick_change")

        # ---------- ЛОГИ ТАЙМ-АУТОВ ----------
        if before.timed_out_until != after.timed_out_until:
            channel = self.get_channel("mod", after.guild.id)
            if not channel:
                return

            entry = await self.find_audit_log_entry(after.guild, discord.AuditLogAction.member_update, target_id=after.id)
            moderator = entry.user if entry else None

            if after.timed_out_until:
                duration = (after.timed_out_until - datetime.now()).total_seconds() // 60
                embed = self.create_embed(
                    title="⏳ **ТАЙМ-АУТ ВЫДАН**",
                    description=f"{after.mention} получил тайм-аут",
                    color=0xED4245,
                    fields=[
                        ("👤 Участник", f"{after.mention} | `{after.id}`", True),
                        ("🛡️ Модератор", moderator.mention if moderator else "`Неизвестно`", True),
                        ("⏱️ Длительность", f"{duration} минут", True),
                        ("📅 Истекает", f"<t:{int(after.timed_out_until.timestamp())}:R>", True)
                    ],
                    thumbnail=after.display_avatar.url
                )
            else:
                embed = self.create_embed(
                    title="✅ **ТАЙМ-АУТ СНЯТ**",
                    description=f"{after.mention} больше не в тайм-ауте",
                    color=0x57F287,
                    fields=[
                        ("👤 Участник", f"{after.mention} | `{after.id}`", True),
                        ("🛡️ Модератор", moderator.mention if moderator else "`Неизвестно`", True)
                    ],
                    thumbnail=after.display_avatar.url
                )
            await self.safe_send(channel, embed, "timeout_update")

    # ---------- ЛОГИ ГЛОБАЛЬНОГО ИМЕНИ ----------
    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        for guild in self.bot.guilds:
            if guild.id == self.allowed_guild_id:
                member = guild.get_member(after.id)
                if member and before.name != after.name:
                    channel = self.get_channel("name", guild.id)
                    if channel:
                        embed = self.create_embed(
                            title="📝 **ИЗМЕНЕНИЕ USERNAME**",
                            description=f"{member.mention} изменил глобальное имя",
                            color=0x5865F2,
                            fields=[
                                ("⬅️ Было", f"`{before.name}`", True),
                                ("➡️ Стало", f"`{after.name}`", True),
                                ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                                ("🕵️ Инициатор", member.mention, True)
                            ],
                            thumbnail=member.display_avatar.url
                        )
                        await self.safe_send(channel, embed, "username_change")
                break

    # ---------- ЛОГИ СООБЩЕНИЙ ----------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or not self.is_allowed_guild(message.guild.id) or message.author.bot:
            return
        channel = self.get_channel("messages", message.guild.id)
        if not channel:
            return

        entry = await self.find_audit_log_entry(message.guild, discord.AuditLogAction.message_delete, target_id=message.id)
        moderator = entry.user if entry else None
        if moderator == message.author:
            moderator = None

        fields = [
            ("👤 Автор", f"{message.author.mention} | `{message.author.id}`", True),
            ("📝 Содержание", f"```{message.content[:500]}```" if message.content else "*Нет текста*", False),
            ("📎 Вложения", str(len(message.attachments)) if message.attachments else "Нет", True)
        ]
        if moderator:
            fields.append(("🗑️ Удалил", moderator.mention, True))

        embed = self.create_embed(
            title="🗑️ **СООБЩЕНИЕ УДАЛЕНО**",
            description=f"В {message.channel.mention}",
            color=0xED4245,
            fields=fields,
            thumbnail=message.author.display_avatar.url
        )
        await self.safe_send(channel, embed, "message_delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or not self.is_allowed_guild(before.guild.id) or before.author.bot or before.content == after.content:
            return
        channel = self.get_channel("messages", before.guild.id)
        if not channel:
            return

        entry = await self.find_audit_log_entry(before.guild, discord.AuditLogAction.message_update, target_id=before.id)
        editor = entry.user if entry else before.author

        embed = self.create_embed(
            title="✏️ **СООБЩЕНИЕ ИЗМЕНЕНО**",
            description=f"[Перейти]({after.jump_url})",
            color=0xFEE75C,
            fields=[
                ("👤 Автор", f"{after.author.mention} | `{after.author.id}`", True),
                ("📌 Канал", after.channel.mention, True),
                ("🛡️ Изменил", editor.mention, True),
                ("⬅️ До", f"```{before.content[:500]}```" if before.content else "*Нет текста*", False),
                ("➡️ После", f"```{after.content[:500]}```" if after.content else "*Нет текста*", False)
            ],
            thumbnail=after.author.display_avatar.url
        )
        await self.safe_send(channel, embed, "message_edit")

    # ---------- ЛОГИ РЕАКЦИЙ ----------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not reaction.message.guild or not self.is_allowed_guild(reaction.message.guild.id) or user.bot:
            return
        channel = self.get_channel("messages", reaction.message.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="➕ **РЕАКЦИЯ ДОБАВЛЕНА**",
            description=f"{user.mention} поставил реакцию в {reaction.message.channel.mention}",
            color=0x57F287,
            fields=[
                ("👤 Пользователь", f"{user.mention} | `{user.id}`", True),
                ("📌 Сообщение", f"[Перейти]({reaction.message.jump_url})", True),
                ("🎉 Реакция", str(reaction.emoji), True),
                ("📝 Содержание", f"```{reaction.message.content[:200]}```" if reaction.message.content else "*Нет текста*", False)
            ],
            thumbnail=user.display_avatar.url
        )
        await self.safe_send(channel, embed, "reaction_add")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if not reaction.message.guild or not self.is_allowed_guild(reaction.message.guild.id) or user.bot:
            return
        channel = self.get_channel("messages", reaction.message.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="➖ **РЕАКЦИЯ УДАЛЕНА**",
            description=f"{user.mention} убрал реакцию в {reaction.message.channel.mention}",
            color=0xED4245,
            fields=[
                ("👤 Пользователь", f"{user.mention} | `{user.id}`", True),
                ("📌 Сообщение", f"[Перейти]({reaction.message.jump_url})", True),
                ("🎉 Реакция", str(reaction.emoji), True)
            ],
            thumbnail=user.display_avatar.url
        )
        await self.safe_send(channel, embed, "reaction_remove")

    @commands.Cog.listener()
    async def on_reaction_clear(self, message, reactions):
        if not message.guild or not self.is_allowed_guild(message.guild.id):
            return
        channel = self.get_channel("messages", message.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="🧹 **РЕАКЦИИ ОЧИЩЕНЫ**",
            description=f"В {message.channel.mention}",
            color=0xFEE75C,
            fields=[
                ("📌 Сообщение", f"[Перейти]({message.jump_url})", True),
                ("📊 Количество реакций", str(len(reactions)), True)
            ],
            thumbnail=message.guild.icon.url if message.guild.icon else None
        )
        await self.safe_send(channel, embed, "reaction_clear")

    # ---------- ЛОГИ ВХОДА/ВЫХОДА ----------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self.is_allowed_guild(member.guild.id):
            return
        channel = self.get_channel("join_leave", member.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="✅ **УЧАСТНИК ЗАШЕЛ**",
            description=f"{member.mention} присоединился",
            color=0x57F287,
            fields=[
                ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                ("📅 Аккаунт создан", f"<t:{int(member.created_at.timestamp())}:R>", True),
                ("📊 Участников", str(len(member.guild.members)), True),
                ("🕵️ Инициатор", member.mention, True)
            ],
            thumbnail=member.display_avatar.url
        )
        await self.safe_send(channel, embed, "member_join")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not self.is_allowed_guild(member.guild.id):
            return

        channel_join = self.get_channel("join_leave", member.guild.id)
        if channel_join:
            embed = self.create_embed(
                title="❌ **УЧАСТНИК ВЫШЕЛ**",
                description=f"{member.mention} покинул сервер",
                color=0xED4245,
                fields=[
                    ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                    ("📅 Зашел", f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "*Неизвестно*", True),
                    ("🎭 Ролей", str(len(member.roles)-1), True),
                    ("🕵️ Инициатор", member.mention, True)
                ],
                thumbnail=member.display_avatar.url
            )
            await self.safe_send(channel_join, embed, "member_leave")

        # Проверка на кик
        async def check_kick():
            await asyncio.sleep(1)
            channel_mod = self.get_channel("mod", member.guild.id)
            if not channel_mod:
                return
            entry = await self.find_audit_log_entry(member.guild, discord.AuditLogAction.kick, target_id=member.id)
            if entry:
                embed = self.create_embed(
                    title="👢 **УЧАСТНИК КИКНУТ**",
                    description="",
                    color=0xED4245,
                    fields=[
                        ("👤 Участник", f"{member.mention} | `{member.id}`", True),
                        ("🛡️ Модератор", entry.user.mention, True),
                        ("📝 Причина", f"```{entry.reason or 'Не указана'}```", False)
                    ],
                    thumbnail=member.display_avatar.url
                )
                await self.safe_send(channel_mod, embed, "member_kick")

        self.bot.loop.create_task(check_kick())

    # ---------- ЛОГИ БАНОВ ----------
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if not self.is_allowed_guild(guild.id):
            return
        channel = self.get_channel("mod", guild.id)
        if not channel:
            return

        entry = await self.find_audit_log_entry(guild, discord.AuditLogAction.ban, target_id=user.id)
        moderator = entry.user if entry else None
        reason = entry.reason if entry else "Не указана"

        embed = self.create_embed(
            title="🔨 **УЧАСТНИК ЗАБАНЕН**",
            description="",
            color=0xED4245,
            fields=[
                ("👤 Участник", f"@{user.name} | `{user.id}`", True),
                ("🛡️ Модератор", moderator.mention if moderator else "`Неизвестно`", True),
                ("📝 Причина", f"```{reason}```", False)
            ],
            thumbnail=user.display_avatar.url if user.display_avatar else None
        )
        await self.safe_send(channel, embed, "member_ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        if not self.is_allowed_guild(guild.id):
            return
        channel = self.get_channel("mod", guild.id)
        if not channel:
            return

        entry = await self.find_audit_log_entry(guild, discord.AuditLogAction.unban, target_id=user.id)
        moderator = entry.user if entry else None

        embed = self.create_embed(
            title="⚡ **УЧАСТНИК РАЗБАНЕН**",
            description="",
            color=0x57F287,
            fields=[
                ("👤 Участник", f"@{user.name} | `{user.id}`", True),
                ("🛡️ Модератор", moderator.mention if moderator else "`Неизвестно`", True),
                ("⏰ Время", f"<t:{int(datetime.now().timestamp())}:R>", True)
            ],
            thumbnail=user.display_avatar.url if user.display_avatar else None
        )
        await self.safe_send(channel, embed, "member_unban")

    # ---------- ЛОГИ ПРИГЛАШЕНИЙ ----------
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if not invite.guild or not self.is_allowed_guild(invite.guild.id):
            return
        channel = self.get_channel("other", invite.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="🔗 **ПРИГЛАШЕНИЕ СОЗДАНО**",
            description="",
            color=0x57F287,
            fields=[
                ("👤 Создатель", f"{invite.inviter.mention} | `{invite.inviter.id}`", True),
                ("📌 Канал", invite.channel.mention if invite.channel else "`Неизвестно`", True),
                ("⏱️ Срок действия", f"Истекает <t:{int(invite.expires_at.timestamp())}:R>" if invite.expires_at else "`Никогда`", True),
                ("🔢 Макс. использований", str(invite.max_uses) if invite.max_uses else "`Безлимитно`", True)
            ]
        )
        await self.safe_send(channel, embed, "invite_create")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if not invite.guild or not self.is_allowed_guild(invite.guild.id):
            return
        channel = self.get_channel("other", invite.guild.id)
        if not channel:
            return

        embed = self.create_embed(
            title="❌ **ПРИГЛАШЕНИЕ УДАЛЕНО**",
            description="",
            color=0xED4245,
            fields=[
                ("👤 Создатель", f"{invite.inviter.mention} | `{invite.inviter.id}`" if invite.inviter else "`Неизвестно`", True),
                ("📌 Канал", invite.channel.mention if invite.channel else "`Неизвестно`", True),
                ("🔢 Использовано раз", str(invite.uses) if invite.uses else "0", True)
            ]
        )
        await self.safe_send(channel, embed, "invite_delete")

    # ---------- ЛОГИ ЗАКРЕПЛЁННЫХ СООБЩЕНИЙ ----------
    @commands.Cog.listener()
    async def on_message_pin(self, message, channel=None):  # для dpy 2.0+
        if not message.guild or not self.is_allowed_guild(message.guild.id):
            return
        log_channel = self.get_channel("messages", message.guild.id)
        if not log_channel:
            return

        embed = self.create_embed(
            title="📌 **СООБЩЕНИЕ ЗАКРЕПЛЕНО**",
            description=f"В {message.channel.mention}",
            color=0x57F287,
            fields=[
                ("👤 Автор", f"{message.author.mention} | `{message.author.id}`", True),
                ("📝 Содержание", f"```{message.content[:200]}```" if message.content else "*Нет текста*", False),
                ("🔗 Ссылка", f"[Перейти]({message.jump_url})", True)
            ],
            thumbnail=message.author.display_avatar.url
        )
        await self.safe_send(log_channel, embed, "message_pin")

    @commands.Cog.listener()
    async def on_message_unpin(self, message, channel=None):
        if not message.guild or not self.is_allowed_guild(message.guild.id):
            return
        log_channel = self.get_channel("messages", message.guild.id)
        if not log_channel:
            return

        embed = self.create_embed(
            title="📌 **СООБЩЕНИЕ ОТКРЕПЛЕНО**",
            description=f"В {message.channel.mention}",
            color=0xED4245,
            fields=[
                ("👤 Автор", f"{message.author.mention} | `{message.author.id}`", True),
                ("📝 Содержание", f"```{message.content[:200]}```" if message.content else "*Нет текста*", False),
                ("🔗 Ссылка", f"[Перейти]({message.jump_url})", True)
            ],
            thumbnail=message.author.display_avatar.url
        )
        await self.safe_send(log_channel, embed, "message_unpin")

    # ---------- ДРУГИЕ ЛОГИ (other) ----------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if not self.is_allowed_guild(channel.guild.id):
            return
        log_channel = self.get_channel("other", channel.guild.id)
        if not log_channel:
            return

        entry = await self.find_audit_log_entry(channel.guild, discord.AuditLogAction.channel_create, target_id=channel.id)
        creator = entry.user if entry else None

        embed = self.create_embed(
            title="📌 **КАНАЛ СОЗДАН**",
            description="",
            color=0x57F287,
            fields=[
                ("📢 Канал", f"{channel.mention} | `{channel.id}`", True),
                ("📁 Тип", f"`{channel.type}`", True),
                ("📌 Категория", channel.category.mention if channel.category else "`Нет`", True),
                ("🛡️ Создал", creator.mention if creator else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "channel_create")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not self.is_allowed_guild(channel.guild.id):
            return
        log_channel = self.get_channel("other", channel.guild.id)
        if not log_channel:
            return

        entry = await self.find_audit_log_entry(channel.guild, discord.AuditLogAction.channel_delete, target_id=channel.id)
        deleter = entry.user if entry else None

        embed = self.create_embed(
            title="🗑️ **КАНАЛ УДАЛЕН**",
            description="",
            color=0xED4245,
            fields=[
                ("📢 Канал", f"`{channel.name}` | `{channel.id}`", True),
                ("📁 Тип", f"`{channel.type}`", True),
                ("📌 Категория", f"`{channel.category.name if channel.category else 'Нет'}`", True),
                ("🛡️ Удалил", deleter.mention if deleter else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "channel_delete")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if not self.is_allowed_guild(after.guild.id):
            return
        log_channel = self.get_channel("other", after.guild.id)
        if not log_channel:
            return

        changes = []
        if before.name != after.name:
            changes.append(f"Название: `{before.name}` → `{after.name}`")
        if before.category != after.category:
            changes.append(f"Категория: {before.category.name if before.category else 'Нет'} → {after.category.name if after.category else 'Нет'}")
        if before.topic != after.topic:
            changes.append(f"Тема: `{before.topic or 'Нет'}` → `{after.topic or 'Нет'}`")
        if before.overwrites != after.overwrites:
            changes.append("Права доступа изменены")

        # Дополнительные поля для голосовых каналов
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            if before.bitrate != after.bitrate:
                changes.append(f"Битрейт: {before.bitrate/1000} кбит/с → {after.bitrate/1000} кбит/с")
            if before.user_limit != after.user_limit:
                changes.append(f"Лимит пользователей: {before.user_limit} → {after.user_limit}")

        if not changes:
            return

        entry = await self.find_audit_log_entry(after.guild, discord.AuditLogAction.channel_update, target_id=after.id)
        editor = entry.user if entry else None

        embed = self.create_embed(
            title="✏️ **КАНАЛ ИЗМЕНЕН**",
            description=f"{after.mention}",
            color=0xFEE75C,
            fields=[
                ("📊 Изменения", "\n".join(changes), False),
                ("🛡️ Изменил", editor.mention if editor else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "channel_update")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not self.is_allowed_guild(role.guild.id):
            return
        log_channel = self.get_channel("other", role.guild.id)
        if not log_channel:
            return

        entry = await self.find_audit_log_entry(role.guild, discord.AuditLogAction.role_create, target_id=role.id)
        creator = entry.user if entry else None

        embed = self.create_embed(
            title="🎭 **РОЛЬ СОЗДАНА**",
            description="",
            color=0x57F287,
            fields=[
                ("🎨 Роль", f"{role.mention} | `{role.id}`", True),
                ("🎨 Цвет", f"`#{role.color.value:06x}`" if role.color.value else "`По умолчанию`", True),
                ("🛡️ Создал", creator.mention if creator else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "role_create")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not self.is_allowed_guild(role.guild.id):
            return
        log_channel = self.get_channel("other", role.guild.id)
        if not log_channel:
            return

        entry = await self.find_audit_log_entry(role.guild, discord.AuditLogAction.role_delete, target_id=role.id)
        deleter = entry.user if entry else None

        embed = self.create_embed(
            title="🗑️ **РОЛЬ УДАЛЕНА**",
            description="",
            color=0xED4245,
            fields=[
                ("🎨 Роль", f"`{role.name}` | `{role.id}`", True),
                ("👥 Участников", str(len(role.members)), True),
                ("🛡️ Удалил", deleter.mention if deleter else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "role_delete")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if not self.is_allowed_guild(after.guild.id):
            return
        log_channel = self.get_channel("other", after.guild.id)
        if not log_channel:
            return

        changes = []
        if before.name != after.name:
            changes.append(f"Название: `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"Цвет: `#{before.color.value:06x}` → `#{after.color.value:06x}`")
        if before.permissions != after.permissions:
            changes.append("Права изменены")
        if before.hoist != after.hoist:
            changes.append(f"Отображать отдельно: {after.hoist}")
        if before.mentionable != after.mentionable:
            changes.append(f"Упоминание: {after.mentionable}")

        if not changes:
            return

        entry = await self.find_audit_log_entry(after.guild, discord.AuditLogAction.role_update, target_id=after.id)
        editor = entry.user if entry else None

        embed = self.create_embed(
            title="✏️ **РОЛЬ ИЗМЕНЕНА**",
            description=f"{after.mention}",
            color=0xFEE75C,
            fields=[
                ("📊 Изменения", "\n".join(changes), False),
                ("🛡️ Изменил", editor.mention if editor else "`Неизвестно`", True)
            ]
        )
        await self.safe_send(log_channel, embed, "role_update")

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if not self.is_allowed_guild(after.id):
            return
        log_channel = self.get_channel("other", after.id)
        if not log_channel:
            return

        if before.name != after.name:
            embed = self.create_embed(
                title="📝 **НАЗВАНИЕ СЕРВЕРА ИЗМЕНЕНО**",
                description="",
                color=0xFEE75C,
                fields=[
                    ("⬅️ Было", f"`{before.name}`", True),
                    ("➡️ Стало", f"`{after.name}`", True)
                ]
            )
            await self.safe_send(log_channel, embed, "guild_name")

        if before.icon != after.icon:
            embed = self.create_embed(
                title="🖼️ **ИКОНКА СЕРВЕРА ИЗМЕНЕНА**",
                description="",
                color=0xFEE75C,
                fields=[
                    ("📌 Сервер", after.name, True)
                ]
            )
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            await self.safe_send(log_channel, embed, "guild_icon")

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(self.allowed_guild_id)
        if guild:
            logger.info(f"""
╔══════════════════════════════════════╗
║  ✅ Система логирования загружена
║  📊 Сервер: {guild.name} ({self.allowed_guild_id})
║  📋 Каналы:""")
            for name, cid in self.log_channels.items():
                ch = self.bot.get_channel(cid)
                if ch:
                    logger.info(f"║     {name}: ✅ #{ch.name} (ID: {cid})")
                else:
                    logger.warning(f"║     {name}: ❌ НЕ НАЙДЕН (ID: {cid})")
            logger.info("╚══════════════════════════════════════╝")
        else:
            logger.warning(f"""
╔══════════════════════════════════════╗
║  ⚠️ Система логирования загружена
║  📊 Сервер {self.allowed_guild_id} НЕ НАЙДЕН
║  📋 Логирование будет пропущено
╚══════════════════════════════════════╝
            """)

async def setup(bot):
    await bot.add_cog(logging_system(bot))