# -*- coding: utf-8 -*-
"""
InfoAudit — смена ника по форме (автоконфиг + кастом шаблон ника).

ФИКС:
1) Persistent view регистрируется один раз в setup()
2) Добавлен on_interaction хук по custom_id="infoaudit:open_modal"
   -> кнопка будет работать и в welcome (components v2 / layout), и после рестартов.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Optional, Dict
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands, InteractionType
from discord.ext import commands

MAX_NICK = 32
CONFIG_FILENAME = "config.json"
DEFAULT_HISTORY_FILE = "infoaudit_history.jsonl"
DEFAULT_ROTATE_MB = 10
DEFAULT_TEMPLATE = "{first_word(server_name)} {static_id}"


# ---------- Utils ----------

def _normalize_ws(s: str) -> str:
    return " ".join(str(s).split())


def _first_word_from_server(server_name: str) -> str:
    if not server_name:
        return ""
    seg = server_name.split("|")[-1].strip()
    return seg.split()[0] if seg else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rotate_if_big(path: str, max_mb: int) -> None:
    try:
        p = Path(path)
        if p.exists() and p.stat().st_size > max_mb * 1024 * 1024:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            p.rename(p.with_name(f"{p.stem}-{ts}{p.suffix}"))
    except Exception:
        pass


def _render_nick_template(template: str, server_name: str, static_id: str) -> str:
    srv = _normalize_ws(server_name)
    sid = _normalize_ws(static_id)
    first = _first_word_from_server(server_name)

    out = template.replace("{first_word(server_name)}", first)
    out = out.replace("{first_word}", first)
    out = out.replace("{server_name}", srv).replace("{static_id}", sid)

    out = _normalize_ws(out).strip()
    return out[:MAX_NICK] if len(out) > MAX_NICK else out


# ---------- Config ----------

@dataclass
class PanelConfig:
    title: str = "Анкета участника"
    description: str = "Нажми кнопку ниже, чтобы заполнить данные. Ник обновится автоматически."
    image_url: Optional[str] = None


@dataclass
class LogsConfig:
    channel_id: Optional[int] = None
    history_file: str = DEFAULT_HISTORY_FILE
    rotate_mb: int = DEFAULT_ROTATE_MB


@dataclass
class NicknameConfig:
    template: str = DEFAULT_TEMPLATE


@dataclass
class InfoConfig:
    panel: PanelConfig = field(default_factory=PanelConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    nickname: NicknameConfig = field(default_factory=NicknameConfig)


# ---------- UI ----------

class InfoModal(discord.ui.Modal, title="Анкета: смена ника"):
    def __init__(self, cog: "InfoAudit"):
        super().__init__(timeout=None)
        self.cog = cog

        self.server_name = discord.ui.TextInput(label="Имя (на сервере)")
        self.static_id = discord.ui.TextInput(label="Static ID")

        self.add_item(self.server_name)
        self.add_item(self.static_id)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.apply_nick_from_values(
            interaction,
            self.server_name.value,
            self.static_id.value
        )


class InfoPanelView(discord.ui.View):
    def __init__(self, cog: "InfoAudit"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Заполнить данные",
        style=discord.ButtonStyle.primary,
        custom_id="infoaudit:open_modal"
    )
    async def open_modal(self, interaction: discord.Interaction, _: discord.ui.Button):
        # Всегда отвечаем быстро
        await interaction.response.send_modal(InfoModal(self.cog))


# ---------- Cog ----------

class InfoAudit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dir = os.path.dirname(__file__)
        self.config_path = os.path.join(self.dir, CONFIG_FILENAME)
        # self.cfg_dir удалён
        self.config = self._ensure_config_file(self.config_path)

    # --- interaction hook: фикс для welcome/components v2 ---
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        Ловим нажатие по custom_id даже если сообщение было отправлено не как обычный view,
        а как layout/components v2 (welcome), где persistent view может не сматчиться стабильно.
        """
        try:
            if interaction.type != InteractionType.component:
                return

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            if custom_id != "infoaudit:open_modal":
                return

            # если уже ответили — выходим
            if interaction.response.is_done():
                return

            await interaction.response.send_modal(InfoModal(self))

        except Exception as e:
            # Без падения, но с логом
            try:
                print(f"[infoaudit] on_interaction error: {e}")
            except Exception:
                pass

    def _ensure_config_file(self, path: str) -> InfoConfig:
        default = {
            "panel": {},
            "logs": {},
            "nickname": {}
        }

        if not os.path.exists(path):
            _ensure_parent(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2, ensure_ascii=False)

        raw = _load_json(path, default)

        return InfoConfig(
            panel=PanelConfig(**(raw.get("panel") or {})),
            logs=LogsConfig(**(raw.get("logs") or {})),
            nickname=NicknameConfig(**(raw.get("nickname") or {}))
        )

    def get_config(self, guild_id=None):
        """
        Возвращает единый конфиг (per‑guild не поддерживается).
        Параметр guild_id сохранён для совместимости, но игнорируется.
        """
        return self.config

    def _build_panel_embed(self, cfg: InfoConfig, guild):
        emb = discord.Embed(
            title=cfg.panel.title,
            description=cfg.panel.description,
            color=discord.Color.blurple()
        )
        if cfg.panel.image_url:
            emb.set_image(url=cfg.panel.image_url)
        return emb

    async def apply_nick_from_values(self, interaction, server_name, static_id):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ Это можно делать только на сервере.", ephemeral=True)
            return

        # interaction.user обычно Member, но на всякий:
        member = interaction.user
        if not isinstance(member, discord.Member):
            member = guild.get_member(interaction.user.id)

        if member is None:
            await interaction.response.send_message("❌ Не удалось получить участника.", ephemeral=True)
            return

        new_nick = _render_nick_template(
            self.config.nickname.template,
            server_name,
            static_id
        )

        try:
            await member.edit(nick=new_nick, reason="InfoAudit: nickname update")
            await interaction.response.send_message(f"✅ Ник установлен: {new_nick}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)

    # ---------- Commands ----------

    @app_commands.command(name="info_panel", description="Показать панель анкеты для смены ника")
    async def info_panel(self, interaction: discord.Interaction):
        cfg = self.get_config(interaction.guild.id if interaction.guild else None)
        embed = self._build_panel_embed(cfg, interaction.guild)
        await interaction.response.send_message(embed=embed, view=InfoPanelView(self))

    @commands.command(name="info_panel")
    async def info_panel_prefix(self, ctx):
        cfg = self.get_config(ctx.guild.id if ctx.guild else None)
        embed = self._build_panel_embed(cfg, ctx.guild)
        await ctx.send(embed=embed, view=InfoPanelView(self))


# ---------- setup ----------

async def setup(bot: commands.Bot):
    cog = InfoAudit(bot)
    await bot.add_cog(cog)

    # Persistent-view (для обычных сообщений/panel). Для welcome всё равно подстраховываемся on_interaction.
    bot.add_view(InfoPanelView(cog))
