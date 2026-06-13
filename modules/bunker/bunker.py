from __future__ import annotations

import asyncio
import json
import math
import random
import secrets
import string
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Any

import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

MODULE_NAME = "bunker"
MODULE_DIR = Path(__file__).parent
CFG_PATH = MODULE_DIR / "bunker_config.json"
DATA_PATH = MODULE_DIR / "bunker_games.json"

DEFAULT_CFG = {
    "enabled": True,
    "web_enabled": True,
    "web_host": "0.0.0.0",
    "web_port": 50227,
    "public_base_url": "",
    "survival_min": 0.3,
    "survival_max": 0.4,
    "min_players": 4,
    "max_players_limit": 20,
    "move_players_to_voice": True,
    "keep_eliminated_in_voice": True,
    "delete_voice_on_end": True,
    "embed_color": 0x5865F2,
}

PROFESSIONS = [
    "Врач", "Инженер", "Фермер", "Повар", "Электрик", "Психолог", "Механик", "Военный медик",
    "Биолог", "Химик", "Строитель", "Охранник", "Учитель", "Программист", "Сантехник", "Ветеринар",
    "Пожарный", "Радиоинженер", "Пилот", "Агроном", "Фармацевт", "Спасатель", "Кинолог", "Архитектор",
]
HEALTH = [
    "Полностью здоров", "Слабое зрение", "Аллергия на пыль", "Быстро устаёт", "Проблемы со спиной",
    "Отличная физическая форма", "Хронический кашель", "Панические атаки", "Плохой слух", "Нуждается в лекарствах",
    "Здоров, но слабый иммунитет", "Сломана рука, скоро восстановится",
]
HOBBIES = [
    "Садоводство", "Рыбалка", "Шахматы", "Ремонт техники", "Кулинария", "Спорт", "Охота", "Чтение",
    "Радиосвязь", "Туризм", "Выращивание растений", "Настольные игры", "Пение", "Рисование", "Самооборона",
]
PHOBIAS = [
    "Темнота", "Замкнутые пространства", "Высота", "Кровь", "Одиночество", "Насекомые", "Громкие звуки",
    "Глубокая вода", "Огонь", "Болезни", "Толпа", "Неизвестность", "Нет фобий",
]
ITEMS = [
    "Аптечка", "Набор инструментов", "Семена овощей", "Фонарик", "Рация", "Фильтр для воды",
    "Тёплая одежда", "Книга по медицине", "Ноутбук", "Солнечная панель", "Консервы", "Карта местности",
    "Набор ножей", "Верёвка", "Аккумулятор", "Огнетушитель", "Спальный мешок", "Респиратор",
]
SKILLS = [
    "Умеет чинить генераторы", "Может лечить людей", "Умеет выращивать еду", "Хорошо готовит",
    "Знает основы выживания", "Умеет договариваться", "Может обучать детей", "Разбирается в электронике",
    "Умеет строить укрытия", "Хорошо ориентируется", "Знает химию и фильтрацию", "Умеет поддерживать дисциплину",
    "Может чинить водопровод", "Знает первую помощь", "Умеет работать с животными",
]
FACTS = [
    "Раньше работал в армии", "Не доверяет незнакомцам", "Скрывает часть прошлого", "Очень стрессоустойчивый",
    "Имеет опыт жизни в деревне", "Был волонтёром", "Умеет быстро принимать решения", "Боится ответственности",
    "Хорошо работает в команде", "Часто спорит с лидерами", "Умеет сохранять спокойствие", "Имеет лидерские качества",
]
CATASTROPHES = [
    ("☢️ Ядерная зима", "После серии взрывов поверхность стала опасной, а климат резко похолодал."),
    ("🦠 Глобальная пандемия", "Неизвестный вирус уничтожил большую часть населения. Нужна изоляция."),
    ("☄️ Падение астероида", "Астероид вызвал пожары, пыль в атмосфере и разрушение инфраструктуры."),
    ("🤖 Восстание ИИ", "Автоматические системы вышли из-под контроля. Города стали небезопасны."),
    ("🌋 Супервулкан", "Извержение закрыло небо пеплом. Еды и чистого воздуха становится меньше."),
    ("🌊 Всемирное наводнение", "Большая часть суши ушла под воду. Бункер стал единственным безопасным местом."),
]
BUNKER_PROBLEMS = [
    "повреждён генератор", "не хватает фильтров воздуха", "сломана система отопления", "часть склада затоплена",
    "нестабильная связь", "мало медикаментов", "нужен ремонт водоснабжения", "плохая вентиляция",
]
ROUND_FIELDS = [
    ("profession", "Профессия"),
    ("health", "Здоровье"),
    ("item", "Предмет"),
    ("skill", "Навык"),
    ("fact", "Факт"),
]


def load_cfg() -> dict:
    if not CFG_PATH.exists():
        CFG_PATH.write_text(json.dumps(DEFAULT_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_CFG, **data}
    except Exception:
        return DEFAULT_CFG.copy()


def save_games(games: dict[str, Any]) -> None:
    DATA_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")


def read_games() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def code_id(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def make_card() -> dict[str, str | int]:
    return {
        "profession": random.choice(PROFESSIONS),
        "age": random.randint(18, 65),
        "health": random.choice(HEALTH),
        "hobby": random.choice(HOBBIES),
        "phobia": random.choice(PHOBIAS),
        "item": random.choice(ITEMS),
        "skill": random.choice(SKILLS),
        "fact": random.choice(FACTS),
    }


@dataclass
class PlayerState:
    id: int
    name: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(12))
    alive: bool = True
    card: dict[str, Any] = field(default_factory=make_card)
    revealed: list[str] = field(default_factory=list)


@dataclass
class GameState:
    id: str
    guild_id: int
    channel_id: int
    host_id: int
    max_players: int
    status: str = "lobby"  # lobby, started, voting, ended
    places: Optional[int] = None
    survival_rate: Optional[float] = None
    catastrophe_title: str = ""
    catastrophe_desc: str = ""
    bunker_problem: str = ""
    voice_channel_id: Optional[int] = None
    message_id: Optional[int] = None
    round_index: int = 0
    players: dict[int, PlayerState] = field(default_factory=dict)
    votes: dict[int, int] = field(default_factory=dict)  # voter_id -> target_id

    def public_url(self, cfg: dict, token: str | None = None) -> str:
        base = (cfg.get("public_base_url") or "").rstrip("/")
        if not base:
            port = int(cfg.get("web_port", 50227))
            base = f"http://localhost:{port}"
        url = f"{base}/bunker/{self.id}"
        if token:
            url += f"?token={token}"
        return url

    def alive_players(self) -> list[PlayerState]:
        return [p for p in self.players.values() if p.alive]

    def current_round(self) -> tuple[str, str]:
        idx = min(self.round_index, len(ROUND_FIELDS) - 1)
        return ROUND_FIELDS[idx]


class BunkerLobbyView(discord.ui.View):
    def __init__(self, cog: "BunkerCog", game_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_id = game_id

    @discord.ui.button(label="Войти", style=discord.ButtonStyle.success, emoji="✅")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.join_game(interaction, self.game_id)

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.leave_game(interaction, self.game_id)

    @discord.ui.button(label="Начать", style=discord.ButtonStyle.primary, emoji="▶️")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.start_game(interaction, self.game_id)


class BunkerGameView(discord.ui.View):
    def __init__(self, cog: "BunkerCog", game_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.game_id = game_id

    @discord.ui.button(label="Раскрыть раунд", style=discord.ButtonStyle.primary, emoji="🃏")
    async def reveal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.reveal_round(interaction, self.game_id)

    @discord.ui.button(label="Голосование", style=discord.ButtonStyle.danger, emoji="🗳️")
    async def vote_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_vote(interaction, self.game_id)

    @discord.ui.button(label="Закончить", style=discord.ButtonStyle.secondary, emoji="⛔")
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.end_game(interaction, self.game_id, manual=True)


class VoteView(discord.ui.View):
    def __init__(self, cog: "BunkerCog", game_id: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.game_id = game_id
        game = cog.games.get(game_id)
        if game:
            for p in game.alive_players()[:25]:
                self.add_item(VoteButton(cog, game_id, p.id, p.name[:80]))

    async def on_timeout(self) -> None:
        await self.cog.finish_vote(self.game_id)


class VoteButton(discord.ui.Button):
    def __init__(self, cog: "BunkerCog", game_id: str, target_id: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.cog = cog
        self.game_id = game_id
        self.target_id = target_id

    async def callback(self, interaction: discord.Interaction):
        await self.cog.cast_vote(interaction, self.game_id, self.target_id)


class BunkerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cfg = load_cfg()
        self.games: dict[str, GameState] = {}
        self.web_runner: Optional[web.AppRunner] = None
        self.web_site: Optional[web.TCPSite] = None
        self.load_saved_games()

    async def cog_load(self):
        if self.cfg.get("web_enabled", True):
            await self.start_web()

    async def cog_unload(self):
        if self.web_runner:
            await self.web_runner.cleanup()

    def load_saved_games(self):
        raw = read_games()
        for gid, g in raw.items():
            try:
                game = GameState(
                    id=g["id"], guild_id=int(g["guild_id"]), channel_id=int(g["channel_id"]), host_id=int(g["host_id"]),
                    max_players=int(g["max_players"]), status=g.get("status", "lobby"), places=g.get("places"),
                    survival_rate=g.get("survival_rate"), catastrophe_title=g.get("catastrophe_title", ""),
                    catastrophe_desc=g.get("catastrophe_desc", ""), bunker_problem=g.get("bunker_problem", ""),
                    voice_channel_id=g.get("voice_channel_id"), message_id=g.get("message_id"), round_index=int(g.get("round_index", 0)),
                    votes={int(k): int(v) for k, v in g.get("votes", {}).items()},
                )
                for pid, p in g.get("players", {}).items():
                    game.players[int(pid)] = PlayerState(
                        id=int(p["id"]), name=p.get("name", "Player"), token=p.get("token", secrets.token_urlsafe(12)),
                        alive=bool(p.get("alive", True)), card=p.get("card") or make_card(), revealed=p.get("revealed", []),
                    )
                self.games[gid] = game
            except Exception:
                continue

    def persist(self):
        raw = {}
        for gid, game in self.games.items():
            d = asdict(game)
            d["players"] = {str(pid): asdict(p) for pid, p in game.players.items()}
            d["votes"] = {str(k): str(v) for k, v in game.votes.items()}
            raw[gid] = d
        save_games(raw)

    def is_host_or_admin(self, user: discord.abc.User, guild: discord.Guild | None, game: GameState) -> bool:
        if user.id == game.host_id:
            return True
        if guild:
            member = guild.get_member(user.id)
            return bool(member and member.guild_permissions.administrator)
        return False

    def lobby_embed(self, game: GameState) -> discord.Embed:
        e = discord.Embed(title="🏚️ Бункер", color=int(self.cfg.get("embed_color", 0x5865F2)))
        e.description = "Набор игроков открыт. Нажмите **Войти**, чтобы попасть в игру."
        e.add_field(name="Игроков", value=f"{len(game.players)}/{game.max_players}", inline=True)
        e.add_field(name="Мест", value="рассчитается при старте", inline=True)
        e.add_field(name="Статус", value=game.status, inline=True)
        if game.players:
            e.add_field(name="Участники", value="\n".join(f"• {p.name}" for p in game.players.values())[:1024], inline=False)
        e.set_footer(text=f"Game ID: {game.id}")
        return e

    def game_embed(self, game: GameState) -> discord.Embed:
        e = discord.Embed(title="☢️ Игра Бункер началась", color=int(self.cfg.get("embed_color", 0x5865F2)))
        e.description = f"**{game.catastrophe_title}**\n{game.catastrophe_desc}"
        e.add_field(name="Игроков", value=str(len(game.players)), inline=True)
        e.add_field(name="Живых", value=str(len(game.alive_players())), inline=True)
        e.add_field(name="Мест", value=str(game.places), inline=True)
        if game.survival_rate:
            e.add_field(name="Шанс выживания", value=f"{round(game.survival_rate * 100)}%", inline=True)
        e.add_field(name="Проблема бункера", value=game.bunker_problem or "неизвестно", inline=True)
        field_key, field_name = game.current_round()
        e.add_field(name="Текущий раунд", value=field_name, inline=True)
        e.add_field(name="Сайт", value=game.public_url(self.cfg), inline=False)
        alive = [f"✅ {p.name}" for p in game.alive_players()]
        dead = [f"❌ {p.name}" for p in game.players.values() if not p.alive]
        e.add_field(name="Игроки", value="\n".join(alive + dead)[:1024] or "—", inline=False)
        e.set_footer(text=f"Game ID: {game.id}")
        return e

    async def refresh_message(self, game: GameState):
        if not game.message_id:
            return
        ch = self.bot.get_channel(game.channel_id)
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            msg = await ch.fetch_message(game.message_id)
            if game.status == "lobby":
                await msg.edit(embed=self.lobby_embed(game), view=BunkerLobbyView(self, game.id))
            elif game.status in ("started", "voting"):
                await msg.edit(embed=self.game_embed(game), view=BunkerGameView(self, game.id))
        except Exception:
            pass

    bunker = app_commands.Group(name="bunker", description="Мини-игра Бункер")

    @bunker.command(name="create", description="Создать игру Бункер")
    @app_commands.describe(players="Максимум игроков, например 10")
    async def create_slash(self, interaction: discord.Interaction, players: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Команда работает только на сервере.", ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Нужны права администратора.", ephemeral=True)
        min_p = int(self.cfg.get("min_players", 4))
        max_lim = int(self.cfg.get("max_players_limit", 20))
        if players < min_p or players > max_lim:
            return await interaction.response.send_message(f"Количество игроков должно быть от {min_p} до {max_lim}.", ephemeral=True)
        gid = code_id()
        while gid in self.games:
            gid = code_id()
        game = GameState(id=gid, guild_id=interaction.guild.id, channel_id=interaction.channel_id, host_id=interaction.user.id, max_players=players)
        self.games[gid] = game
        self.persist()
        embed = self.lobby_embed(game)
        await interaction.response.send_message(embed=embed, view=BunkerLobbyView(self, gid))
        msg = await interaction.original_response()
        game.message_id = msg.id
        self.persist()

    @bunker.command(name="card", description="Получить ссылку на свою карточку")
    async def card_slash(self, interaction: discord.Interaction):
        game = self.find_user_game(interaction.user.id, interaction.guild_id)
        if not game:
            return await interaction.response.send_message("Ты сейчас не в игре Бункер.", ephemeral=True)
        p = game.players.get(interaction.user.id)
        if not p:
            return await interaction.response.send_message("Карточка не найдена.", ephemeral=True)
        await interaction.response.send_message(embed=self.private_card_embed(game, p), ephemeral=True)

    @bunker.command(name="end", description="Закончить активную игру")
    async def end_slash(self, interaction: discord.Interaction):
        game = self.find_guild_game(interaction.guild_id)
        if not game:
            return await interaction.response.send_message("Активная игра не найдена.", ephemeral=True)
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            return await interaction.response.send_message("Закончить может ведущий или админ.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self.end_game(interaction, game.id, manual=True)

    def find_guild_game(self, guild_id: int | None) -> Optional[GameState]:
        if guild_id is None:
            return None
        for g in self.games.values():
            if g.guild_id == guild_id and g.status != "ended":
                return g
        return None

    def find_user_game(self, user_id: int, guild_id: int | None) -> Optional[GameState]:
        for g in self.games.values():
            if guild_id is not None and g.guild_id != guild_id:
                continue
            if user_id in g.players and g.status != "ended":
                return g
        return None

    async def join_game(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status != "lobby":
            return await interaction.response.send_message("Лобби уже закрыто.", ephemeral=True)
        if interaction.user.id in game.players:
            return await interaction.response.send_message("Ты уже в игре.", ephemeral=True)
        if len(game.players) >= game.max_players:
            return await interaction.response.send_message("Лобби заполнено.", ephemeral=True)
        name = getattr(interaction.user, "display_name", interaction.user.name)
        game.players[interaction.user.id] = PlayerState(id=interaction.user.id, name=name)
        self.persist()
        await self.refresh_message(game)
        await interaction.response.send_message("✅ Ты вошёл в игру.", ephemeral=True)

    async def leave_game(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status != "lobby":
            return await interaction.response.send_message("Выйти можно только до старта.", ephemeral=True)
        if interaction.user.id not in game.players:
            return await interaction.response.send_message("Ты не в игре.", ephemeral=True)
        game.players.pop(interaction.user.id, None)
        self.persist()
        await self.refresh_message(game)
        await interaction.response.send_message("🚪 Ты вышел из игры.", ephemeral=True)

    async def start_game(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status != "lobby":
            return await interaction.response.send_message("Игру нельзя начать.", ephemeral=True)
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            return await interaction.response.send_message("Начать может ведущий или админ.", ephemeral=True)
        min_p = int(self.cfg.get("min_players", 4))
        if len(game.players) < min_p:
            return await interaction.response.send_message(f"Нужно минимум {min_p} игрока.", ephemeral=True)
        smin = float(self.cfg.get("survival_min", 0.3))
        smax = float(self.cfg.get("survival_max", 0.4))
        game.survival_rate = random.uniform(smin, smax)
        game.places = max(1, math.ceil(len(game.players) * game.survival_rate))
        title, desc = random.choice(CATASTROPHES)
        game.catastrophe_title = title
        game.catastrophe_desc = desc
        game.bunker_problem = random.choice(BUNKER_PROBLEMS)
        game.status = "started"
        await self.create_voice_and_move(interaction.guild, game)
        self.persist()
        await self.send_private_cards(game)
        await self.refresh_message(game)
        await interaction.response.send_message(f"▶️ Игра началась. Мест в бункере: **{game.places}**.", ephemeral=True)

    async def create_voice_and_move(self, guild: discord.Guild | None, game: GameState):
        if not guild:
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True),
        }
        members = []
        for p in game.players.values():
            m = guild.get_member(p.id)
            if m:
                overwrites[m] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
                members.append(m)
        category = None
        ch = self.bot.get_channel(game.channel_id)
        if isinstance(ch, discord.TextChannel):
            category = ch.category
        try:
            voice = await guild.create_voice_channel(name=f"🎙️ Бункер {game.id}", overwrites=overwrites, category=category)
            game.voice_channel_id = voice.id
            if self.cfg.get("move_players_to_voice", True):
                for m in members:
                    try:
                        if m.voice and m.voice.channel:
                            await m.move_to(voice)
                    except Exception:
                        pass
        except Exception:
            game.voice_channel_id = None

    def private_card_embed(self, game: GameState, p: PlayerState) -> discord.Embed:
        c = p.card
        e = discord.Embed(title="👤 Твоя карточка Бункера", color=int(self.cfg.get("embed_color", 0x5865F2)))
        e.add_field(name="Профессия", value=str(c.get("profession")), inline=True)
        e.add_field(name="Возраст", value=str(c.get("age")), inline=True)
        e.add_field(name="Здоровье", value=str(c.get("health")), inline=False)
        e.add_field(name="Хобби", value=str(c.get("hobby")), inline=True)
        e.add_field(name="Фобия", value=str(c.get("phobia")), inline=True)
        e.add_field(name="Предмет", value=str(c.get("item")), inline=False)
        e.add_field(name="Навык", value=str(c.get("skill")), inline=False)
        e.add_field(name="Факт", value=str(c.get("fact")), inline=False)
        e.add_field(name="Сайт", value=game.public_url(self.cfg, p.token), inline=False)
        return e

    async def send_private_cards(self, game: GameState):
        for p in game.players.values():
            user = self.bot.get_user(p.id)
            if not user:
                try:
                    user = await self.bot.fetch_user(p.id)
                except Exception:
                    continue
            try:
                await user.send(embed=self.private_card_embed(game, p))
            except Exception:
                pass

    async def reveal_round(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status not in ("started", "voting"):
            return await interaction.response.send_message("Игра не запущена.", ephemeral=True)
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            return await interaction.response.send_message("Раскрыть раунд может ведущий или админ.", ephemeral=True)
        key, title = game.current_round()
        lines = []
        for p in game.alive_players():
            val = p.card.get(key, "—")
            p.revealed.append(key) if key not in p.revealed else None
            lines.append(f"**{p.name}** — {val}")
        e = discord.Embed(title=f"🃏 Раунд: {title}", description="\n".join(lines)[:4000], color=int(self.cfg.get("embed_color", 0x5865F2)))
        if game.round_index < len(ROUND_FIELDS) - 1:
            game.round_index += 1
        self.persist()
        await self.refresh_message(game)
        await interaction.response.send_message(embed=e)

    async def open_vote(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status not in ("started", "voting"):
            return await interaction.response.send_message("Игра не запущена.", ephemeral=True)
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            return await interaction.response.send_message("Голосование запускает ведущий или админ.", ephemeral=True)
        game.status = "voting"
        game.votes = {}
        self.persist()
        e = discord.Embed(title="🗳️ Голосование", description="Кого выгнать из бункера? Голосуют только живые игроки.\nВремя: 3 минуты.", color=0xED4245)
        await interaction.response.send_message(embed=e, view=VoteView(self, game_id))

    async def cast_vote(self, interaction: discord.Interaction, game_id: str, target_id: int):
        game = self.games.get(game_id)
        if not game or game.status != "voting":
            return await interaction.response.send_message("Сейчас нет активного голосования.", ephemeral=True)
        voter = game.players.get(interaction.user.id)
        target = game.players.get(target_id)
        if not voter or not voter.alive:
            return await interaction.response.send_message("Голосовать могут только живые игроки.", ephemeral=True)
        if not target or not target.alive:
            return await interaction.response.send_message("Этот игрок уже выбыл.", ephemeral=True)
        if target_id == interaction.user.id:
            return await interaction.response.send_message("За себя голосовать нельзя.", ephemeral=True)
        game.votes[interaction.user.id] = target_id
        self.persist()
        await interaction.response.send_message(f"✅ Голос принят против **{target.name}**.", ephemeral=True)
        if len(game.votes) >= len(game.alive_players()):
            await self.finish_vote(game_id)

    async def finish_vote(self, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status != "voting":
            return
        ch = self.bot.get_channel(game.channel_id)
        counts: dict[int, int] = {}
        for target_id in game.votes.values():
            counts[target_id] = counts.get(target_id, 0) + 1
        if not counts:
            game.status = "started"
            self.persist()
            if isinstance(ch, discord.TextChannel):
                await ch.send("🗳️ Голосование завершено: никто не проголосовал.")
            return
        max_votes = max(counts.values())
        losers = [pid for pid, n in counts.items() if n == max_votes]
        loser_id = random.choice(losers)
        loser = game.players.get(loser_id)
        if loser:
            loser.alive = False
        game.votes = {}
        game.status = "started"
        self.persist()
        if isinstance(ch, discord.TextChannel):
            await ch.send(f"❌ Из бункера выгнан: **{loser.name if loser else loser_id}**. Голосов: **{max_votes}**.")
        if loser and not self.cfg.get("keep_eliminated_in_voice", True):
            guild = self.bot.get_guild(game.guild_id)
            if guild:
                m = guild.get_member(loser.id)
                if m and m.voice:
                    try:
                        await m.move_to(None)
                    except Exception:
                        pass
        if game.places is not None and len(game.alive_players()) <= game.places:
            await self.end_game_by_state(game)
        else:
            await self.refresh_message(game)

    async def end_game(self, interaction: discord.Interaction, game_id: str, manual: bool = False):
        game = self.games.get(game_id)
        if not game:
            return
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            if not interaction.response.is_done():
                return await interaction.response.send_message("Закончить может ведущий или админ.", ephemeral=True)
            return
        await self.end_game_by_state(game, manual=manual)
        if not interaction.response.is_done():
            await interaction.response.send_message("⛔ Игра завершена.", ephemeral=True)

    async def end_game_by_state(self, game: GameState, manual: bool = False):
        game.status = "ended"
        ch = self.bot.get_channel(game.channel_id)
        alive = game.alive_players()
        lines = [f"**{p.name}** — {p.card.get('profession', '—')}" for p in alive]
        e = discord.Embed(title="🎉 Финал Бункера", color=0x57F287)
        e.description = "Игра завершена вручную." if manual else "В бункере осталось нужное количество людей."
        e.add_field(name="Выжившие", value="\n".join(lines)[:1024] or "Нет выживших", inline=False)
        if isinstance(ch, discord.TextChannel):
            await ch.send(embed=e)
        if self.cfg.get("delete_voice_on_end", True) and game.voice_channel_id:
            vc = self.bot.get_channel(game.voice_channel_id)
            if isinstance(vc, discord.VoiceChannel):
                try:
                    await vc.delete(reason="Bunker game ended")
                except Exception:
                    pass
        self.persist()

    async def start_web(self):
        app = web.Application()
        app.router.add_get("/bunker/{game_id}", self.web_game)
        app.router.add_get("/bunker_api/{game_id}", self.web_api_game)
        app.router.add_post("/bunker_api/{game_id}/vote", self.web_api_vote)
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        self.web_site = web.TCPSite(self.web_runner, self.cfg.get("web_host", "0.0.0.0"), int(self.cfg.get("web_port", 50227)))
        await self.web_site.start()
        print(f"[Bunker] web started on {self.cfg.get('web_host')}:{self.cfg.get('web_port')}")

    def _player_by_token(self, game: GameState, token: str | None) -> Optional[PlayerState]:
        if not token:
            return None
        for p in game.players.values():
            if p.token == token:
                return p
        return None

    async def web_game(self, request: web.Request):
        gid = request.match_info["game_id"]
        token = request.query.get("token", "")
        html = f"""<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Бункер {gid}</title>
<style>body{{margin:0;background:#0f1117;color:#fff;font-family:Arial,sans-serif}}.wrap{{max-width:1000px;margin:0 auto;padding:24px}}.card{{background:#181b24;border:1px solid #2b3040;border-radius:16px;padding:18px;margin:12px 0}}button{{background:#5865f2;color:white;border:0;border-radius:10px;padding:10px 14px;margin:5px;cursor:pointer}}button.danger{{background:#ed4245}}.muted{{color:#aeb4c2}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}</style>
</head><body><div class=\"wrap\"><h1>🏚️ Бункер</h1><div id=\"app\">Загрузка...</div></div>
<script>
const GAME_ID = {json.dumps(gid)}; const TOKEN = {json.dumps(token)};
async function load(){{ const r=await fetch(`/bunker_api/${{GAME_ID}}?token=${{encodeURIComponent(TOKEN)}}`); const d=await r.json(); render(d); }}
async function vote(id){{ await fetch(`/bunker_api/${{GAME_ID}}/vote?token=${{encodeURIComponent(TOKEN)}}`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{target_id:id}})}}); await load(); }}
function esc(s){{return String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
function render(d){{ if(d.error){{document.getElementById('app').innerHTML=`<div class=card>Ошибка: ${{esc(d.error)}}</div>`;return;}}
let card=''; if(d.me){{card=`<div class=card><h2>👤 Моя карточка</h2><div class=grid>${{Object.entries(d.me.card).map(([k,v])=>`<div><b>${{esc(k)}}</b><br>${{esc(v)}}</div>`).join('')}}</div></div>`}}
let vote=''; if(d.can_vote){{vote=`<div class=card><h2>🗳️ Голосование</h2>${{d.players.filter(p=>p.alive && (!d.me || p.id!==d.me.id)).map(p=>`<button class=danger onclick="vote('${{p.id}}')">${{esc(p.name)}}</button>`).join('')}}</div>`}}
document.getElementById('app').innerHTML=`<div class=card><h2>${{esc(d.catastrophe.title||'Ожидание старта')}}</h2><p>${{esc(d.catastrophe.desc||'')}}</p><p class=muted>Статус: ${{esc(d.status)}} | Игроков: ${{d.players.length}}/${{d.max_players}} | Мест: ${{d.places??'?' }} | Шанс: ${{d.survival_rate?Math.round(d.survival_rate*100)+'%':'?'}}</p><p>Проблема бункера: <b>${{esc(d.bunker_problem||'будет выбрана при старте')}}</b></p></div><div class=card><h2>Игроки</h2>${{d.players.map(p=>`<p>${{p.alive?'✅':'❌'}} ${{esc(p.name)}} ${{p.revealed && p.revealed.length ? '<span class=muted>— раскрыто: '+esc(p.revealed.join(', '))+'</span>' : ''}}</p>`).join('')}}</div>${{card}}${{vote}}`; }}
load(); setInterval(load, 5000);
</script></body></html>"""
        return web.Response(text=html, content_type="text/html")

    async def web_api_game(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        players = []
        for p in game.players.values():
            players.append({"id": str(p.id), "name": p.name, "alive": p.alive, "revealed": [dict(ROUND_FIELDS).get(k, k) for k in p.revealed]})
        data = {
            "id": game.id, "status": game.status, "max_players": game.max_players, "places": game.places,
            "survival_rate": game.survival_rate, "bunker_problem": game.bunker_problem,
            "catastrophe": {"title": game.catastrophe_title, "desc": game.catastrophe_desc},
            "players": players, "can_vote": bool(me and me.alive and game.status == "voting"),
            "me": None,
        }
        if me:
            data["me"] = {"id": str(me.id), "name": me.name, "alive": me.alive, "card": {
                "Профессия": me.card.get("profession"), "Возраст": me.card.get("age"), "Здоровье": me.card.get("health"),
                "Хобби": me.card.get("hobby"), "Фобия": me.card.get("phobia"), "Предмет": me.card.get("item"),
                "Навык": me.card.get("skill"), "Факт": me.card.get("fact"),
            }}
        return web.json_response(data)

    async def web_api_vote(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        if not me or not me.alive or game.status != "voting":
            return web.json_response({"error": "cant_vote"}, status=403)
        body = await request.json()
        target_id = int(body.get("target_id"))
        target = game.players.get(target_id)
        if not target or not target.alive or target.id == me.id:
            return web.json_response({"error": "bad_target"}, status=400)
        game.votes[me.id] = target_id
        self.persist()
        if len(game.votes) >= len(game.alive_players()):
            asyncio.create_task(self.finish_vote(game.id))
        return web.json_response({"ok": True})


async def setup(bot: commands.Bot):
    await bot.add_cog(BunkerCog(bot))
