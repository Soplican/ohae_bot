import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands, tasks

MODULE_NAME = "birthday"
log = logging.getLogger(f"Phantom_Bot.modules.{MODULE_NAME}")

MODULE_DIR = Path("modules") / MODULE_NAME
CFG_PATH = MODULE_DIR / "birthday_config.json"
DATA_PATH = MODULE_DIR / "birthday_data.json"

DEFAULT_CFG = {
    "enabled": True,
    "default_message": "🎉 С днём рождения, {mention}! Сегодня твой день! 🎂",
    "default_emojis": ["🎉", "🎂", "🎁"],
    "embed_color": 0xFFAA00,
    "birthday_role_id": None,
    "birthday_channel_id": None,
}


def _ensure_files() -> None:
    MODULE_DIR.mkdir(parents=True, exist_ok=True)
    if not CFG_PATH.exists():
        CFG_PATH.write_text(json.dumps(DEFAULT_CFG, indent=2, ensure_ascii=False), encoding="utf-8")
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps({"guilds": {}}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_cfg() -> dict:
    _ensure_files()
    try:
        data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_CFG, **data}
    except Exception:
        log.exception("Failed to load birthday_config.json")
        return DEFAULT_CFG.copy()


def load_data() -> dict:
    _ensure_files()
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if "guilds" not in data or not isinstance(data["guilds"], dict):
            data["guilds"] = {}
        return data
    except Exception:
        log.exception("Failed to load birthday_data.json")
        return {"guilds": {}}


def save_data(data: dict) -> None:
    _ensure_files()
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def guild_data(data: dict, guild_id: int) -> dict:
    gid = str(guild_id)
    guilds = data.setdefault("guilds", {})
    if gid not in guilds:
        cfg = load_cfg()
        guilds[gid] = {
            "enabled": True,
            "channel_id": cfg.get("birthday_channel_id"),
            "birthday_role_id": cfg.get("birthday_role_id"),
            "message": cfg.get("default_message"),
            "emojis": cfg.get("default_emojis", ["🎉", "🎂", "🎁"]),
            "users": {},
            "active": {},
        }
    g = guilds[gid]
    g.setdefault("enabled", True)
    g.setdefault("channel_id", None)
    g.setdefault("birthday_role_id", None)
    g.setdefault("message", load_cfg().get("default_message"))
    g.setdefault("emojis", ["🎉", "🎂", "🎁"])
    g.setdefault("users", {})
    g.setdefault("active", {})
    return g


def parse_birthday(value: str) -> tuple[int, int, Optional[int]]:
    raw = value.strip().replace("/", ".").replace("-", ".")
    parts = [p for p in raw.split(".") if p]
    if len(parts) not in (2, 3):
        raise ValueError("Формат: DD.MM или DD.MM.YYYY")
    day = int(parts[0])
    month = int(parts[1])
    year = int(parts[2]) if len(parts) == 3 else None
    if year is not None:
        datetime(year, month, day)
    else:
        datetime(2000, month, day)
    return day, month, year


def format_date(user_data: dict) -> str:
    day = int(user_data["day"])
    month = int(user_data["month"])
    year = user_data.get("year")
    return f"{day:02d}.{month:02d}" + (f".{year}" if year else "")


def calc_age(year: Optional[int]) -> Optional[int]:
    if not year:
        return None
    return max(0, datetime.now().year - int(year))


def days_until(day: int, month: int) -> int:
    today = datetime.now().date()
    year = today.year
    while True:
        try:
            target = datetime(year, month, day).date()
        except ValueError:
            # 29 февраля: если год не високосный, пробуем следующий
            year += 1
            continue
        if target >= today:
            return (target - today).days
        year += 1


def is_admin_member(member: discord.Member) -> bool:
    return bool(getattr(member, "guild_permissions", None) and member.guild_permissions.administrator)


def build_birthday_embed(member: discord.Member, udata: dict, message_template: str, color: int) -> discord.Embed:
    age = calc_age(udata.get("year"))
    profile = udata.get("profile") or {}

    text = (message_template or "🎉 С днём рождения, {mention}! 🎂")
    text = (text
            .replace("{mention}", member.mention)
            .replace("{user}", str(member))
            .replace("{name}", member.display_name)
            .replace("{server}", member.guild.name)
            .replace("{age}", str(age) if age is not None else ""))

    embed = discord.Embed(
        title="🎂 Happy Birthday!",
        description=text,
        color=color,
        timestamp=datetime.now(),
    )
    embed.set_thumbnail(url=str(member.display_avatar.url))
    embed.add_field(name="Именинник", value=f"{member.mention}", inline=True)
    embed.add_field(name="Дата", value=format_date(udata), inline=True)
    if age is not None:
        embed.add_field(name="Возраст", value=f"{age}", inline=True)

    extra = []
    if profile.get("color"):
        extra.append(f"**Любимый цвет:** {profile['color']}")
    if profile.get("game"):
        extra.append(f"**Любимая игра:** {profile['game']}")
    if profile.get("music"):
        extra.append(f"**Любимая музыка:** {profile['music']}")
    if extra:
        embed.add_field(name="Профиль", value="\n".join(extra), inline=False)

    embed.set_footer(text="Birthday Event активен на 24 часа")
    return embed


class BirthdayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    @tasks.loop(minutes=30)
    async def check_birthdays(self):
        await self.bot.wait_until_ready()
        cfg = load_cfg()
        if not cfg.get("enabled", True):
            return

        data = load_data()
        now = datetime.now()
        current_year = now.year
        changed = False

        for guild in self.bot.guilds:
            gdata = guild_data(data, guild.id)
            if not gdata.get("enabled", True):
                continue

            # remove expired active events and birthday role
            active = gdata.setdefault("active", {})
            for uid, info in list(active.items()):
                try:
                    until = datetime.fromisoformat(info.get("until"))
                except Exception:
                    until = now
                if until <= now:
                    member = guild.get_member(int(uid))
                    role_id = gdata.get("birthday_role_id")
                    if member and role_id:
                        role = guild.get_role(int(role_id))
                        if role and role in member.roles:
                            try:
                                await member.remove_roles(role, reason="Birthday event expired")
                            except Exception:
                                log.exception("Failed to remove birthday role")
                    active.pop(uid, None)
                    changed = True

            todays = []
            for uid, udata in list(gdata.get("users", {}).items()):
                if int(udata.get("day", 0)) == now.day and int(udata.get("month", 0)) == now.month:
                    if int(udata.get("announced_year", 0)) != current_year:
                        member = guild.get_member(int(uid))
                        if member:
                            todays.append((member, udata))

            if not todays:
                continue

            channel = None
            channel_id = gdata.get("channel_id")
            if channel_id:
                channel = guild.get_channel(int(channel_id))
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(int(channel_id))
                    except Exception:
                        channel = None
            if channel is None:
                channel = guild.system_channel

            for member, udata in todays:
                embed = build_birthday_embed(
                    member,
                    udata,
                    gdata.get("message") or cfg.get("default_message"),
                    int(cfg.get("embed_color", 0xFFAA00)),
                )
                if channel:
                    try:
                        await channel.send(content=member.mention, embed=embed)
                    except Exception:
                        log.exception("Failed to send birthday embed")

                role_id = gdata.get("birthday_role_id")
                if role_id:
                    role = guild.get_role(int(role_id))
                    me = guild.me
                    if role and me and me.guild_permissions.manage_roles and me.top_role > role:
                        try:
                            await member.add_roles(role, reason="Birthday event started")
                        except Exception:
                            log.exception("Failed to add birthday role")

                udata["announced_year"] = current_year
                active[str(member.id)] = {
                    "until": (now + timedelta(hours=24)).isoformat(timespec="seconds")
                }
                changed = True

        if changed:
            save_data(data)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        data = load_data()
        gdata = guild_data(data, message.guild.id)
        active = gdata.get("active", {})
        info = active.get(str(message.author.id))
        if not info:
            return

        try:
            until = datetime.fromisoformat(info.get("until"))
        except Exception:
            until = datetime.now()
        if until <= datetime.now():
            active.pop(str(message.author.id), None)
            save_data(data)
            return

        emojis = gdata.get("emojis") or ["🎉", "🎂", "🎁"]
        for emoji in emojis[:3]:
            try:
                await message.add_reaction(str(emoji))
            except (discord.Forbidden, discord.HTTPException):
                pass

    @commands.group(name="birthday", invoke_without_command=True)
    async def birthday(self, ctx: commands.Context):
        await ctx.send(
            "🎂 **Birthday commands:**\n"
            "`!birthday set DD.MM` или `!birthday set DD.MM.YYYY`\n"
            "`!birthday remove`\n"
            "`!birthday check @user`\n"
            "`!birthday upcoming` / `!birthday list`\n"
            "`!birthday profile color/game/music <текст>`\n"
            "Админ: `!birthday channel #channel`, `!birthday role @role`, `!birthday message <текст>`, `!birthday emojis 🎉 🎂 🎁`, `!birthday stats`, `!birthday test @user`"
        )

    @birthday.command(name="set")
    async def birthday_set(self, ctx: commands.Context, date: str):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        day, month, year = parse_birthday(date)
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        gdata["users"][str(ctx.author.id)] = {
            "day": day,
            "month": month,
            "year": year,
            "profile": gdata.get("users", {}).get(str(ctx.author.id), {}).get("profile", {}),
        }
        save_data(data)
        saved = f"{day:02d}.{month:02d}" + (f".{year}" if year else "")
        await ctx.send(f"✅ Твой день рождения сохранён: `{saved}`")

    @birthday.command(name="remove")
    async def birthday_remove(self, ctx: commands.Context):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        gdata.get("users", {}).pop(str(ctx.author.id), None)
        gdata.get("active", {}).pop(str(ctx.author.id), None)
        save_data(data)
        await ctx.send("✅ Твой день рождения удалён.")

    @birthday.command(name="check")
    async def birthday_check(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        member = member or ctx.author
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        udata = gdata.get("users", {}).get(str(member.id))
        if not udata:
            return await ctx.send(f"❌ У {member.mention} день рождения не указан.")
        left = days_until(int(udata["day"]), int(udata["month"]))
        await ctx.send(f"🎂 {member.mention}: `{format_date(udata)}` — через `{left}` дн.")

    @birthday.command(name="upcoming", aliases=["list"])
    async def birthday_upcoming(self, ctx: commands.Context, limit: int = 10):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        limit = max(1, min(limit, 20))
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        items = []
        for uid, udata in gdata.get("users", {}).items():
            member = ctx.guild.get_member(int(uid))
            if not member:
                continue
            left = days_until(int(udata["day"]), int(udata["month"]))
            items.append((left, member, udata))
        if not items:
            return await ctx.send("Пока нет сохранённых дней рождения.")
        items.sort(key=lambda x: x[0])
        lines = []
        for i, (left, member, udata) in enumerate(items[:limit], start=1):
            when = "сегодня" if left == 0 else f"через {left} дн."
            lines.append(f"`{i}.` {member.mention} — `{format_date(udata)}` — **{when}**")
        embed = discord.Embed(title="📅 Ближайшие дни рождения", description="\n".join(lines), color=load_cfg().get("embed_color", 0xFFAA00))
        await ctx.send(embed=embed)

    @birthday.group(name="profile", invoke_without_command=True)
    async def birthday_profile(self, ctx: commands.Context):
        await ctx.send("Используй: `!birthday profile color <цвет>`, `game <игра>`, `music <музыка>`, `show`")

    async def _set_profile_value(self, ctx: commands.Context, key: str, value: str):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        uid = str(ctx.author.id)
        if uid not in gdata["users"]:
            return await ctx.send("Сначала укажи дату: `!birthday set DD.MM`")
        gdata["users"][uid].setdefault("profile", {})[key] = value[:100]
        save_data(data)
        await ctx.send("✅ Профиль обновлён.")

    @birthday_profile.command(name="color")
    async def profile_color(self, ctx: commands.Context, *, value: str):
        await self._set_profile_value(ctx, "color", value)

    @birthday_profile.command(name="game")
    async def profile_game(self, ctx: commands.Context, *, value: str):
        await self._set_profile_value(ctx, "game", value)

    @birthday_profile.command(name="music")
    async def profile_music(self, ctx: commands.Context, *, value: str):
        await self._set_profile_value(ctx, "music", value)

    @birthday_profile.command(name="show")
    async def profile_show(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if ctx.guild is None:
            return await ctx.send("Эта команда работает только на сервере.")
        member = member or ctx.author
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)
        udata = gdata.get("users", {}).get(str(member.id))
        if not udata:
            return await ctx.send("❌ День рождения не указан.")
        embed = build_birthday_embed(member, udata, "Профиль {mention}", load_cfg().get("embed_color", 0xFFAA00))
        await ctx.send(embed=embed)

    @birthday.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def birthday_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["channel_id"] = channel.id
        save_data(data)
        await ctx.send(f"✅ Канал поздравлений: {channel.mention}")

    @birthday.command(name="role")
    @commands.has_permissions(administrator=True)
    async def birthday_role(self, ctx: commands.Context, role: discord.Role):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["birthday_role_id"] = role.id
        save_data(data)
        await ctx.send(f"✅ Birthday Role: {role.mention}")

    @birthday.command(name="message")
    @commands.has_permissions(administrator=True)
    async def birthday_message(self, ctx: commands.Context, *, message: str):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["message"] = message[:1000]
        save_data(data)
        await ctx.send("✅ Текст поздравления сохранён. Плейсхолдеры: `{mention}`, `{user}`, `{name}`, `{server}`, `{age}`")

    @birthday.command(name="emojis")
    @commands.has_permissions(administrator=True)
    async def birthday_emojis(self, ctx: commands.Context, e1: str, e2: str, e3: str):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["emojis"] = [e1, e2, e3]
        save_data(data)
        await ctx.send(f"✅ Эмодзи Birthday Event: {e1} {e2} {e3}")

    @birthday.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def birthday_stats(self, ctx: commands.Context):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        users = gdata.get("users", {})
        now = datetime.now()
        total = len(users)
        month = sum(1 for u in users.values() if int(u.get("month", 0)) == now.month)
        today = sum(1 for u in users.values() if int(u.get("month", 0)) == now.month and int(u.get("day", 0)) == now.day)
        active = len(gdata.get("active", {}))
        embed = discord.Embed(title="📊 Birthday Stats", color=load_cfg().get("embed_color", 0xFFAA00))
        embed.add_field(name="Всего", value=str(total), inline=True)
        embed.add_field(name="В этом месяце", value=str(month), inline=True)
        embed.add_field(name="Сегодня", value=str(today), inline=True)
        embed.add_field(name="Активных Birthday Event", value=str(active), inline=True)
        await ctx.send(embed=embed)

    @birthday.command(name="test")
    @commands.has_permissions(administrator=True)
    async def birthday_test(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        uid = str(member.id)
        udata = gdata.get("users", {}).get(uid) or {"day": datetime.now().day, "month": datetime.now().month, "year": None, "profile": {}}
        embed = build_birthday_embed(member, udata, gdata.get("message"), load_cfg().get("embed_color", 0xFFAA00))
        await ctx.send(content=member.mention, embed=embed)
        gdata.setdefault("active", {})[uid] = {"until": (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")}
        save_data(data)
        await ctx.send("✅ Тестовый Birthday Event включён на 24 часа.")

    @birthday.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def birthday_enable(self, ctx: commands.Context):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["enabled"] = True
        save_data(data)
        await ctx.send("✅ Birthday module включён на этом сервере.")

    @birthday.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def birthday_disable(self, ctx: commands.Context):
        data = load_data()
        gdata = guild_data(data, ctx.guild.id)  # type: ignore
        gdata["enabled"] = False
        save_data(data)
        await ctx.send("✅ Birthday module выключен на этом сервере.")


async def setup(bot: commands.Bot):
    await bot.add_cog(BirthdayCog(bot))
