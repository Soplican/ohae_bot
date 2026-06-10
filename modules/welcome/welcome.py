import json
from pathlib import Path
import logging
import traceback

import discord
from discord.ext import commands
from discord import ui

log = logging.getLogger("ManceraBOT.modules.welcome")

CFG_PATH = Path("modules") / "welcome" / "welcome_config.json"


# ================= CONFIG =================

def load_cfg(guild_id: int | None = None) -> dict:
    """Загружает единый конфиг welcome_config.json (per-guild не поддерживается)."""
    if not CFG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CFG_PATH}")
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


# ================= FORMAT =================

def fmt(text: str, member: discord.Member) -> str:
    if not isinstance(text, str):
        return ""
    return (text
            .replace("{mention}", member.mention)
            .replace("{user}", str(member))
            .replace("{name}", member.display_name)
            .replace("{id}", str(member.id))
            .replace("{server}", member.guild.name if member.guild else "")
            .replace("{avatar}", str(member.display_avatar.url)))


# ================= BUILD WELCOME (Components v2) =================

def build_layout_view(cfg: dict, member: discord.Member) -> ui.LayoutView:
    title = fmt(cfg.get("title", ""), member).strip()
    greeting = fmt(cfg.get("greeting", ""), member).strip()
    footer = fmt(cfg.get("footer_text", ""), member).strip()

    parts: list = []

    if title:
        parts.append(ui.TextDisplay(f"**{title}**"))
    if greeting:
        parts.append(ui.TextDisplay(greeting))

    for row in cfg.get("rows", []):
        rtype = (row.get("type") or "").lower().strip()

        if rtype == "separator":
            parts.append(ui.Separator())
            continue

        if rtype == "heading":
            txt = fmt(row.get("text", ""), member).strip()
            if txt:
                parts.append(ui.TextDisplay(f"**{txt}**"))
            continue

        if rtype == "text":
            txt = fmt(row.get("text", ""), member).strip()
            if txt:
                parts.append(ui.TextDisplay(txt))
            continue

        if rtype == "section":
            txt = fmt(row.get("text", ""), member).strip()
            b = row.get("button") or {}

            accessory = None
            kind = (b.get("kind") or "").lower()

            if kind == "infoaudit":
                accessory = ui.Button(
                    label=b.get("label", "Анкета"),
                    emoji=b.get("emoji"),
                    style=discord.ButtonStyle.primary,
                    custom_id="infoaudit:open_modal"
                )

            elif b.get("url"):
                accessory = ui.Button(
                    style=discord.ButtonStyle.link,
                    label=b.get("label", "Open"),
                    url=b.get("url"),
                    emoji=b.get("emoji")
                )

            if txt:
                if accessory:
                    parts.append(ui.Section(ui.TextDisplay(txt), accessory=accessory))
                else:
                    parts.append(ui.Section(ui.TextDisplay(txt)))
            continue

    media_url = (cfg.get("media") or {}).get("url")
    if media_url:
        gallery = ui.MediaGallery()
        gallery.add_item(media=media_url)
        parts.append(gallery)

    if footer:
        parts.append(ui.TextDisplay(footer))

    container = ui.Container(*parts)
    view = ui.LayoutView()
    view.add_item(container)
    return view


# ================= BUILD LEAVE (Embed thumbnail) =================

def build_leave_embed(cfg: dict, member: discord.Member) -> discord.Embed:
    title = fmt(cfg.get("title", ""), member).strip()
    text = fmt(cfg.get("text", ""), member).strip()
    footer = fmt(cfg.get("footer_text", ""), member).strip()

    show_name_line = bool(cfg.get("show_name_line", True))

    name_line = ""
    if show_name_line:
        name_line = f"**{member.display_name}** ({member.mention})"

    desc_parts = []
    if name_line:
        desc_parts.append(name_line)
    if text:
        desc_parts.append(text)

    embed = discord.Embed(
        title=title if title else None,
        description="\n".join(desc_parts) if desc_parts else None
    )
    embed.set_thumbnail(url=str(member.display_avatar.url))
    if footer:
        embed.set_footer(text=footer)
    return embed


# ================= ROLES (Auto-assign) =================

async def try_assign_roles(member: discord.Member, cfg: dict) -> None:
    """
    Assign roles to a member on join.
    Config format:
      "auto_roles": {
        "enabled": true,
        "role_ids": ["123", "456"]
      }
    role_ids MUST be strings (snowflake-safe for JS dashboard).
    """
    auto = cfg.get("auto_roles") or {}
    if not auto.get("enabled", False):
        return

    role_ids = auto.get("role_ids") or []
    if not isinstance(role_ids, list) or not role_ids:
        return

    # Permissions check
    me = member.guild.me  # type: ignore
    if me is None or not me.guild_permissions.manage_roles:
        log.warning("[auto_roles] Bot has no Manage Roles permission")
        return

    roles_to_add: list[discord.Role] = []
    for rid in role_ids:
        try:
            rid_int = int(str(rid))
        except Exception:
            log.warning(f"[auto_roles] Bad role id (not int): {rid!r}")
            continue

        role = member.guild.get_role(rid_int)
        if role is None:
            log.warning(f"[auto_roles] Role not found: {rid_int}")
            continue

        # Hierarchy check: bot top role must be higher than target role
        if me.top_role <= role:
            log.warning(f"[auto_roles] Can't assign role выше/равна роли бота: {role.name} ({role.id})")
            continue

        roles_to_add.append(role)

    if not roles_to_add:
        return

    # Avoid re-adding existing roles
    roles_to_add = [r for r in roles_to_add if r not in member.roles]
    if not roles_to_add:
        return

    try:
        await member.add_roles(*roles_to_add, reason="Auto roles on join (welcome module)")
        log.info(f"[auto_roles] Added roles to {member} ({member.id}): {[r.id for r in roles_to_add]}")
    except Exception:
        log.error("AUTO ROLES ERROR:\n" + traceback.format_exc())


# ================= COG =================

class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_welcome(self, channel: discord.abc.Messageable, member: discord.Member):
        cfg = load_cfg(member.guild.id if member and member.guild else None)
        view = build_layout_view(cfg, member)
        await channel.send(view=view)

    async def _send_leave(self, channel: discord.abc.Messageable, member: discord.Member):
        cfg = load_cfg(member.guild.id if member and member.guild else None)
        leave_cfg = cfg.get("leave") or {}
        embed = build_leave_embed(leave_cfg, member)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            cfg = load_cfg(member.guild.id if member and member.guild else None)
            if not cfg.get("enabled", True):
                return

            # 1) Roles first (optional)
            await try_assign_roles(member, cfg)

            # 2) Welcome message
            channel_id = int(cfg["channel_id"])
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)

            await self._send_welcome(channel, member)
            log.info(f"[welcome] sent for {member} ({member.id})")

        except Exception:
            log.error("WELCOME ERROR:\n" + traceback.format_exc())

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            cfg = load_cfg(member.guild.id if member and member.guild else None)

            leave_cfg = cfg.get("leave")
            if not leave_cfg or not leave_cfg.get("enabled", False):
                return

            channel_id = int(leave_cfg["channel_id"])
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)

            await self._send_leave(channel, member)
            log.info(f"[leave] sent for {member} ({member.id})")

        except Exception:
            log.error("LEAVE ERROR:\n" + traceback.format_exc())

    @commands.command()
    async def welcome_test(self, ctx: commands.Context):
        try:
            await self._send_welcome(ctx.channel, ctx.author)
        except Exception:
            await ctx.send("Ошибка, смотри консоль.")
            log.error("WELCOME TEST ERROR:\n" + traceback.format_exc())

    @commands.command()
    async def leave_test(self, ctx: commands.Context):
        try:
            cfg = load_cfg(ctx.guild.id if ctx.guild else None)
            leave_cfg = cfg.get("leave")
            if not leave_cfg:
                return await ctx.send("❌ В конфиге нет блока `leave`")

            embed = build_leave_embed(leave_cfg, ctx.author)
            await ctx.send(embed=embed)

        except Exception:
            await ctx.send("Ошибка, смотри консоль.")
            log.error("LEAVE TEST ERROR:\n" + traceback.format_exc())

    @commands.command()
    async def roles_test(self, ctx: commands.Context):
        """Проверка выдачи ролей (выдаст роли тебе)."""
        try:
            cfg = load_cfg(ctx.guild.id if ctx.guild else None)
            await try_assign_roles(ctx.author, cfg)  # type: ignore
            await ctx.send("✅ roles_test: попробовал выдать роли (см. логи).")
        except Exception:
            await ctx.send("Ошибка, смотри консоль.")
            log.error("ROLES TEST ERROR:\n" + traceback.format_exc())


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
