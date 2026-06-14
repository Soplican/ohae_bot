from __future__ import annotations

import asyncio
import json
import math
import random
import secrets
import time
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
STATS_PATH = MODULE_DIR / "bunker_stats.json"
PACK_PATH = MODULE_DIR / "bunker_pack.json"

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
    "round_seconds": 180,
    "ai_catastrophes": True,
    "random_events_enabled": True,
    "stats_enabled": True,
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
    ("hobby", "Хобби"),
    ("phobia", "Фобия"),
    ("baggage", "Багаж"),
    ("backpack", "Рюкзак"),
    ("skill", "Навык"),
    ("fact", "Факт"),
    ("special_card", "Спецкарта"),
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




def read_stats() -> dict[str, Any]:
    if not STATS_PATH.exists():
        return {}
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_stats(stats: dict[str, Any]) -> None:
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


SAFE_REPLACEMENTS = {
    "Порноактер": "Актёр независимого кино",
    "Вебкам-модель": "Стример",
    "Закладчик": "Кладоискатель",
    "Наемный убийца": "Бывший телохранитель",
    "Производитель взрывчатки": "Пиротехник",
    "Порно": "Кино",
    "порно": "кино",
    "Героин 3гр": "Загадочный порошок в пакете",
    "Суицидальные мысли": "Тяжёлый стресс",
    "Копрофил": "Очень странные привычки",
    "Убил бабушку из-за пенсии": "Имеет тёмное прошлое",
    "Снимался в порно": "Снимался в низкобюджетном кино",
    "Стопка журналов для взрослых": "Стопка старых журналов",
    "Презервативы": "Набор латексных изделий",
}


def safe_text(value: Any) -> str:
    text = str(value).strip()
    for bad, good in SAFE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def add_history(game: "GameState", text: str) -> None:
    stamp = time.strftime("%H:%M")
    game.history.append(f"[{stamp}] {text}")
    if len(game.history) > 80:
        game.history = game.history[-80:]


def generate_ai_catastrophe() -> tuple[str, str]:
    causes = ["автономный ИИ", "неизвестный вирус", "солнечная буря", "военный эксперимент", "климатический коллапс", "сбой орбитальных систем"]
    effects = ["разрушил инфраструктуру", "оставил города без энергии", "заразил большую часть поверхности", "заблокировал связь", "изменил климат", "сделал воду опасной"]
    needs = ["чистая вода", "ремонт генератора", "медицинский контроль", "строгая дисциплина", "выращивание еды", "защита входа"]
    c = random.choice(causes)
    e = random.choice(effects)
    n = random.choice(needs)
    title = "🧠 Сгенерированная катастрофа"
    desc = f"После катастрофы {c} {e}. Для выживания бункеру критически нужны: {n}."
    return title, desc


RANDOM_EVENTS = [
    ("⚠️ Найдены припасы", "В старом отсеке нашли дополнительные ресурсы. Мест в бункере стало на 1 больше.", "places_plus"),
    ("⚠️ Повреждение фильтров", "Часть фильтров воздуха вышла из строя. Мест в бункере стало на 1 меньше.", "places_minus"),
    ("⚠️ Медосмотр", "Все игроки должны раскрыть здоровье.", "reveal_health"),
    ("⚠️ Проверка вещей", "Все игроки должны раскрыть багаж.", "reveal_baggage"),
    ("⚠️ Технический сбой", "Бункеру срочно нужен полезный навык. Все раскрывают навык.", "reveal_skill"),
]

def code_id(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def load_pack() -> dict[str, list[str]]:
    """Загружает полный пак карточек из bunker_pack.json.
    Если файла нет или он повреждён, используются встроенные списки.
    """
    fallback = {
        "professions": PROFESSIONS,
        "health": HEALTH,
        "hobbies": HOBBIES,
        "phobias": PHOBIAS,
        "baggage": ITEMS,
        "backpacks": ITEMS,
        "facts": FACTS,
        "special_cards": [
            "Игрок получает дополнительный багаж",
            "Игрок получает второй случайный факт о себе",
            "Увеличивает количество мест в бункере на 1",
            "Уменьшает количество мест в бункере на 1",
        ],
    }
    if not PACK_PATH.exists():
        return fallback
    try:
        data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        result = {}
        for key, default in fallback.items():
            values = data.get(key) or default
            clean = [safe_text(v) for v in values if safe_text(v)]
            result[key] = clean or default
        return result
    except Exception:
        return fallback


def choose_from_pack(key: str, fallback: list[str]) -> str:
    pack = load_pack()
    return random.choice(pack.get(key) or fallback)


def make_card() -> dict[str, str | int]:
    return {
        "profession": choose_from_pack("professions", PROFESSIONS),
        "age": random.randint(18, 65),
        "health": choose_from_pack("health", HEALTH),
        "hobby": choose_from_pack("hobbies", HOBBIES),
        "phobia": choose_from_pack("phobias", PHOBIAS),
        "baggage": choose_from_pack("baggage", ITEMS),
        "backpack": choose_from_pack("backpacks", ITEMS),
        "skill": random.choice(SKILLS),
        "fact": choose_from_pack("facts", FACTS),
        "special_card": choose_from_pack("special_cards", ["Игрок получает дополнительный багаж"]),
    }

@dataclass
class PlayerState:
    id: int
    name: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(12))
    alive: bool = True
    card: dict[str, Any] = field(default_factory=make_card)
    revealed: list[str] = field(default_factory=list)
    special_used: bool = False


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
    history: list[str] = field(default_factory=list)
    round_ends_at: Optional[float] = None
    current_event: str = ""

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

    @discord.ui.button(label="Событие", style=discord.ButtonStyle.success, emoji="⚠️")
    async def event_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.trigger_event(interaction, self.game_id)

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
                    history=g.get("history", []), round_ends_at=g.get("round_ends_at"), current_event=g.get("current_event", ""),
                )
                for pid, p in g.get("players", {}).items():
                    game.players[int(pid)] = PlayerState(
                        id=int(p["id"]), name=p.get("name", "Player"), token=p.get("token", secrets.token_urlsafe(12)),
                        alive=bool(p.get("alive", True)), card=p.get("card") or make_card(), revealed=p.get("revealed", []),
                        special_used=bool(p.get("special_used", False)),
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
        if game.current_event:
            e.add_field(name="Событие", value=game.current_event[:1024], inline=False)
        if game.round_ends_at:
            left = max(0, int(game.round_ends_at - time.time()))
            e.add_field(name="Таймер", value=f"{left//60:02d}:{left%60:02d}", inline=True)
        if game.history:
            e.add_field(name="История", value="\n".join(game.history[-5:])[:1024], inline=False)
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

    @bunker.command(name="pack", description="Показать, сколько карточек загружено в Бункер")
    async def pack_slash(self, interaction: discord.Interaction):
        pack = load_pack()
        text = (
            f"Профессии: **{len(pack.get('professions', []))}**\n"
            f"Здоровье: **{len(pack.get('health', []))}**\n"
            f"Хобби: **{len(pack.get('hobbies', []))}**\n"
            f"Фобии: **{len(pack.get('phobias', []))}**\n"
            f"Багаж: **{len(pack.get('baggage', []))}**\n"
            f"Рюкзак: **{len(pack.get('backpacks', []))}**\n"
            f"Факты: **{len(pack.get('facts', []))}**\n"
            f"Спецкарты: **{len(pack.get('special_cards', []))}**"
        )
        await interaction.response.send_message(text, ephemeral=True)

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
        title, desc = generate_ai_catastrophe() if self.cfg.get("ai_catastrophes", True) else random.choice(CATASTROPHES)
        game.catastrophe_title = title
        game.catastrophe_desc = desc
        game.bunker_problem = random.choice(BUNKER_PROBLEMS)
        game.status = "started"
        game.round_ends_at = time.time() + int(self.cfg.get("round_seconds", 180))
        add_history(game, f"Игра началась. Мест: {game.places}, шанс: {round(game.survival_rate * 100)}%")
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
        e.add_field(name="Багаж", value=str(c.get("baggage", c.get("item", "—"))), inline=False)
        e.add_field(name="Рюкзак", value=str(c.get("backpack", "—")), inline=False)
        e.add_field(name="Навык", value=str(c.get("skill")), inline=False)
        e.add_field(name="Факт", value=str(c.get("fact")), inline=False)
        e.add_field(name="Спецкарта", value=str(c.get("special_card", "—")), inline=False)
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
        add_history(game, f"Раскрыт раунд: {title}")
        if game.round_index < len(ROUND_FIELDS) - 1:
            game.round_index += 1
        game.round_ends_at = time.time() + int(self.cfg.get("round_seconds", 180))
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
        game.round_ends_at = time.time() + 180
        add_history(game, "Запущено голосование")
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
            add_history(game, f"Выгнан игрок: {loser.name}")
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
        self.update_stats(game)
        if self.cfg.get("delete_voice_on_end", True) and game.voice_channel_id:
            vc = self.bot.get_channel(game.voice_channel_id)
            if isinstance(vc, discord.VoiceChannel):
                try:
                    await vc.delete(reason="Bunker game ended")
                except Exception:
                    pass
        self.persist()


    def update_stats(self, game: GameState):
        if not self.cfg.get("stats_enabled", True):
            return
        stats = read_stats()
        alive_ids = {p.id for p in game.alive_players()}
        for p in game.players.values():
            key = str(p.id)
            rec = stats.get(key, {"name": p.name, "games": 0, "wins": 0, "losses": 0})
            rec["name"] = p.name
            rec["games"] = int(rec.get("games", 0)) + 1
            if p.id in alive_ids:
                rec["wins"] = int(rec.get("wins", 0)) + 1
            else:
                rec["losses"] = int(rec.get("losses", 0)) + 1
            stats[key] = rec
        save_stats(stats)

    async def trigger_event(self, interaction: discord.Interaction, game_id: str):
        game = self.games.get(game_id)
        if not game or game.status not in ("started", "voting"):
            return await interaction.response.send_message("Игра не запущена.", ephemeral=True)
        if not self.is_host_or_admin(interaction.user, interaction.guild, game):
            return await interaction.response.send_message("Событие запускает ведущий или админ.", ephemeral=True)
        title, desc, action = random.choice(RANDOM_EVENTS)
        if action == "places_plus" and game.places is not None:
            game.places += 1
        elif action == "places_minus" and game.places is not None:
            game.places = max(1, game.places - 1)
        elif action.startswith("reveal_"):
            key = action.replace("reveal_", "")
            for p in game.alive_players():
                if key not in p.revealed:
                    p.revealed.append(key)
        game.current_event = f"{title}\n{desc}"
        add_history(game, f"Событие: {title}")
        self.persist()
        await self.refresh_message(game)
        await interaction.response.send_message(embed=discord.Embed(title=title, description=desc, color=0xFEE75C))

    def apply_special_card(self, game: GameState, player: PlayerState) -> str:
        if player.special_used:
            return "Спецкарта уже использована."
        text = str(player.card.get("special_card", ""))
        player.special_used = True
        low = text.lower()
        if "увелич" in low and "мест" in low and game.places is not None:
            game.places += 1
            result = "+1 место в бункере."
        elif "уменьш" in low and "мест" in low and game.places is not None:
            game.places = max(1, game.places - 1)
            result = "-1 место в бункере."
        elif "дополнительный багаж" in low:
            player.card["extra_baggage"] = choose_from_pack("baggage", ITEMS)
            result = f"Получен дополнительный багаж: {player.card['extra_baggage']}"
        elif "дополнительный рюкзак" in low:
            player.card["extra_backpack"] = choose_from_pack("backpacks", ITEMS)
            result = f"Получен дополнительный рюкзак: {player.card['extra_backpack']}"
        elif "второй случайный факт" in low or "второй" in low and "факт" in low:
            player.card["extra_fact"] = choose_from_pack("facts", FACTS)
            result = f"Получен дополнительный факт: {player.card['extra_fact']}"
        elif "второе случайное хобби" in low or "второе" in low and "хобби" in low:
            player.card["extra_hobby"] = choose_from_pack("hobbies", HOBBIES)
            result = f"Получено второе хобби: {player.card['extra_hobby']}"
        elif "вторую случайную профессию" in low or "двух област" in low:
            player.card["extra_profession"] = choose_from_pack("professions", PROFESSIONS)
            result = f"Получена вторая профессия: {player.card['extra_profession']}"
        elif "здоров" in low:
            player.card["health"] = choose_from_pack("health", HEALTH)
            result = f"Здоровье изменено: {player.card['health']}"
        elif "фоби" in low:
            player.card["phobia"] = choose_from_pack("phobias", PHOBIAS)
            result = f"Фобия изменена: {player.card['phobia']}"
        elif "хобби" in low:
            player.card["hobby"] = choose_from_pack("hobbies", HOBBIES)
            result = f"Хобби изменено: {player.card['hobby']}"
        elif "багаж" in low:
            player.card["baggage"] = choose_from_pack("baggage", ITEMS)
            result = f"Багаж изменён: {player.card['baggage']}"
        elif "рюкзак" in low:
            player.card["backpack"] = choose_from_pack("backpacks", ITEMS)
            result = f"Рюкзак изменён: {player.card['backpack']}"
        elif "професс" in low:
            player.card["profession"] = choose_from_pack("professions", PROFESSIONS)
            result = f"Профессия изменена: {player.card['profession']}"
        else:
            # Универсальный эффект для сложных карт, которые требуют выбора игрока.
            player.card["extra_fact"] = choose_from_pack("facts", FACTS)
            result = f"Сложная карта применена как бонусный факт: {player.card['extra_fact']}"
        add_history(game, f"{player.name} использовал спецкарту")
        self.persist()
        return result

    async def start_web(self):
        app = web.Application()
        app.router.add_get("/", self.web_home)
        app.router.add_get("/bunker/{game_id}", self.web_game)
        app.router.add_get("/bunker_api/{game_id}", self.web_api_game)
        app.router.add_post("/bunker_api/{game_id}/vote", self.web_api_vote)
        app.router.add_post("/bunker_api/{game_id}/special", self.web_api_special)
        app.router.add_post("/bunker_api/{game_id}/reveal", self.web_api_reveal)
        app.router.add_post("/bunker_api/{game_id}/admin", self.web_api_admin)
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

    def _is_web_host(self, game: GameState, player: PlayerState | None) -> bool:
        return bool(player and player.id == game.host_id)

    def _field_map_ru(self) -> dict[str, str]:
        return dict(ROUND_FIELDS) | {"age": "Возраст"}

    def _field_value(self, p: PlayerState, key: str) -> Any:
        if key == "age":
            return p.card.get("age", "—")
        return p.card.get(key, "—")

    def _public_player_card(self, p: PlayerState, ended: bool = False) -> dict[str, str]:
        out = {}
        keys = ["profession", "age", "health", "hobby", "phobia", "baggage", "backpack", "skill", "fact", "special_card"]
        fmap = self._field_map_ru()
        for key in keys:
            title = fmap.get(key, key)
            if ended or key in p.revealed:
                out[title] = str(self._field_value(p, key))
            else:
                out[title] = "Не раскрывал"
        return out

    async def web_home(self, request: web.Request):
        html = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ohae</title>
<style>
:root{--bg:#070912;--panel:#121827;--line:#283044;--muted:#9aa6bd;--text:#f7f8ff;--accent:#7c5cff;--accent2:#00d4ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0,#26325b 0,#070912 48%),linear-gradient(135deg,#070912,#101524);color:var(--text);font-family:Inter,Arial,sans-serif}.wrap{max-width:1120px;margin:0 auto;padding:40px 20px}.hero{padding:34px;border:1px solid var(--line);border-radius:30px;background:linear-gradient(180deg,rgba(25,32,52,.88),rgba(13,17,29,.92));box-shadow:0 24px 80px #0009}.logo{font-size:46px;margin:0}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:20px}.card{background:rgba(18,24,39,.86);border:1px solid var(--line);border-radius:22px;padding:20px;transition:.15s}.card:hover{transform:translateY(-2px);border-color:#4c5a87}.pill{display:inline-block;background:linear-gradient(135deg,var(--accent),var(--accent2));padding:8px 12px;border-radius:999px;font-weight:800}a{color:#aebcff}</style></head><body><div class=wrap><div class=hero><div class=pill>Ohae Web</div><h1 class=logo>🌐 Панель модулей</h1><p class=muted>Красивый сайт для Discord-игр и модулей.</p><div class=grid><div class=card><h2>🏚️ Бункер</h2><p class=muted>Карточки игроков, голосования, спецкарты, таймеры, replay и статистика.</p></div><div class=card><h2>🎂 Birthday</h2><p class=muted>Поздравления и события дня рождения.</p></div><div class=card><h2>📊 Dashboard</h2><p class=muted>Управление сервером и модулями.</p></div></div></div></div></body></html>"""
        return web.Response(text=html, content_type="text/html")

    async def web_game(self, request: web.Request):
        gid = request.match_info["game_id"]
        token = request.query.get("token", "")
        html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Бункер {gid}</title>
<style>
:root{{--bg:#070912;--panel:#121827;--panel2:#192033;--soft:#202940;--line:#303b58;--text:#f7f8ff;--muted:#9aa6bd;--accent:#7c5cff;--accent2:#00d4ff;--danger:#ff4d6d;--good:#35d07f;--warn:#ffd166}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% -10%,#2c3766 0,#070912 48%),radial-gradient(circle at 100% 0,#371e42 0,#070912 35%);color:var(--text);font-family:Inter,Arial,sans-serif}}.wrap{{max-width:1440px;margin:0 auto;padding:22px}}.top{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px}}h1{{margin:0;font-size:34px}}.badge{{background:rgba(32,41,64,.86);border:1px solid var(--line);border-radius:999px;padding:10px 14px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:1.35fr .65fr;gap:16px}}.panel,.player,.mycard,.field{{background:linear-gradient(180deg,rgba(25,32,51,.92),rgba(14,18,31,.94));border:1px solid var(--line);border-radius:24px;padding:18px;box-shadow:0 18px 55px #0007}}.cat{{min-height:250px;background:linear-gradient(135deg,rgba(124,92,255,.28),rgba(18,24,39,.95) 45%,rgba(255,77,109,.18));position:relative;overflow:hidden}}.cat:after{{content:'☢';position:absolute;right:18px;bottom:-34px;font-size:170px;opacity:.07}}.muted{{color:var(--muted)}}button{{background:linear-gradient(135deg,var(--accent),#5d77ff);color:white;border:0;border-radius:14px;padding:11px 14px;margin:5px;cursor:pointer;font-weight:800;box-shadow:0 8px 24px #0005}}button:hover{{filter:brightness(1.08)}}button:disabled{{opacity:.45;cursor:not-allowed}}button.danger{{background:linear-gradient(135deg,#ff4d6d,#c92a45)}}button.good{{background:linear-gradient(135deg,#22aa68,#35d07f)}}button.ghost{{background:#232c44}}.stat{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}.stat span{{background:rgba(32,41,64,.8);border:1px solid var(--line);border-radius:15px;padding:10px 12px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.field{{padding:14px;border-radius:18px}}.field b{{display:block;margin-bottom:6px}}.field.revealed{{border-color:rgba(53,208,127,.55)}}.field.hidden{{opacity:.8}}.field.clickable{{cursor:pointer}}.field.clickable:hover{{border-color:var(--accent2);transform:translateY(-1px)}}.player{{padding:16px}}.alive{{border-color:rgba(53,208,127,.55)}}.dead{{opacity:.55}}.history{{max-height:380px;overflow:auto}}.history p{{margin:8px 0;color:#d9ddef}}.timer{{font-size:44px;font-weight:950;color:var(--warn);letter-spacing:1px;margin-top:8px}}.vote-card{{display:flex;align-items:center;justify-content:space-between;gap:10px;background:rgba(32,41,64,.85);border:1px solid var(--line);border-radius:18px;padding:12px;margin:8px 0}}.admin-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px}}.theme-row{{display:flex;gap:6px;flex-wrap:wrap}}.theme-dot{{width:34px;height:34px;border-radius:50%;border:2px solid #fff3;cursor:pointer}}.nuclear{{--accent:#7c5cff;--accent2:#00d4ff}}.virus{{--accent:#25c26e;--accent2:#a3ff12}}.ice{{--accent:#54b6ff;--accent2:#c8f5ff}}.fire{{--accent:#ff7a18;--accent2:#ff2f5f}}.space{{--accent:#9b5cff;--accent2:#ff5cbb}}a{{color:#b7c4ff}}@media(max-width:980px){{.grid{{grid-template-columns:1fr}}.top{{align-items:flex-start;flex-direction:column}}}}
</style></head><body class="nuclear"><div class="wrap"><div class="top"><div><h1>🏚️ Бункер</h1><div class="muted">Game ID: {gid}</div></div><div class="badge" id="topStatus">Загрузка...</div></div><div id="app">Загрузка...</div></div>
<script>
const GAME_ID = {json.dumps(gid)}; const TOKEN = {json.dumps(token)}; let last=null;
const fieldTitles={{profession:'Профессия',age:'Возраст',health:'Здоровье',hobby:'Хобби',phobia:'Фобия',baggage:'Багаж',backpack:'Рюкзак',skill:'Навык',fact:'Факт',special_card:'Спецкарта'}};
async function api(path, body){{ const r=await fetch(`/bunker_api/${{GAME_ID}}/${{path}}?token=${{encodeURIComponent(TOKEN)}}`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body||{{}})}}); const d=await r.json().catch(()=>({{}})); if(!r.ok) alert('Ошибка: '+(d.error||r.status)); await load(); return d; }}
async function load(){{ const r=await fetch(`/bunker_api/${{GAME_ID}}?token=${{encodeURIComponent(TOKEN)}}&t=${{Date.now()}}`); const d=await r.json(); last=d; render(d); updateClock(); }}
function esc(s){{return String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
function tleft(ts){{ if(!ts)return '—'; const left=Math.max(0, Math.floor(ts-Date.now()/1000)); return String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0'); }}
function updateClock(){{ if(last){{ const el=document.getElementById('timer'); if(el) el.textContent=tleft(last.round_ends_at); const st=document.getElementById('topStatus'); if(st) st.textContent=`${{last.status}} • ${{last.players.length}}/${{last.max_players}} игроков`; }} }}
function setTheme(t){{ document.body.className=t; localStorage.setItem('bunker_theme',t); }}
function themePanel(){{return `<div class=panel><h2>🎨 Тема</h2><div class=theme-row><div class=theme-dot style="background:linear-gradient(135deg,#7c5cff,#00d4ff)" onclick="setTheme('nuclear')"></div><div class=theme-dot style="background:linear-gradient(135deg,#25c26e,#a3ff12)" onclick="setTheme('virus')"></div><div class=theme-dot style="background:linear-gradient(135deg,#54b6ff,#c8f5ff)" onclick="setTheme('ice')"></div><div class=theme-dot style="background:linear-gradient(135deg,#ff7a18,#ff2f5f)" onclick="setTheme('fire')"></div><div class=theme-dot style="background:linear-gradient(135deg,#9b5cff,#ff5cbb)" onclick="setTheme('space')"></div></div></div>`}}
function fieldHtml(k, title, val, clickable, revealed){{return `<div class="field ${{revealed?'revealed':'hidden'}} ${{clickable?'clickable':''}}" ${{clickable?`onclick="api('reveal',{{field:'${{k}}'}})"`:''}}><b>${{esc(title)}}</b><span class=muted>${{esc(val)}}</span>${{clickable?'<br><small>Нажми, чтобы раскрыть</small>':''}}</div>`}}
function myCard(d){{ if(!d.me) return '<div class=panel><h2>👤 Моя карточка</h2><p class=muted>Открой личную ссылку с token из Discord.</p></div>'; let html='<div class=mycard><h2>👤 Моя карточка</h2><div class=cards>'; for(const [k,title] of Object.entries(fieldTitles)){{ const val=d.me.card[title]??'—'; const rev=d.me.revealed_keys.includes(k); const clickable=d.me.alive && d.status!='ended' && !rev; html+=fieldHtml(k,title,val,clickable,rev); }} html+='</div></div>'; return html; }}
function publicPlayerCard(p){{ let fields=Object.entries(p.card||{{}}).map(([k,v])=>`<div class="field ${{v==='Не раскрывал'?'hidden':'revealed'}}"><b>${{esc(k)}}</b><span class=muted>${{esc(v)}}</span></div>`).join(''); return `<div class="player ${{p.alive?'alive':'dead'}}"><h3>${{p.alive?'✅':'❌'}} ${{esc(p.name)}}</h3><div class=cards>${{fields}}</div></div>` }}
function adminPanel(d){{ if(!d.is_host) return ''; return `<div class=panel><h2>🎛️ Панель ведущего</h2><div class=admin-grid><button onclick="api('admin',{{action:'next_round'}})">След. раунд</button><button onclick="api('admin',{{action:'vote'}})" class=danger>Голосование</button><button onclick="api('admin',{{action:'event'}})" class=good>Событие</button><button onclick="api('admin',{{action:'finish_vote'}})" class=ghost>Итог голос.</button><button onclick="api('admin',{{action:'end'}})" class=danger>Закончить</button></div><p class=muted>Эта панель видна только ведущему по личной ссылке.</p></div>` }}
function presenterPanel(d){{ if(!d.is_host) return ''; return `<div class=panel><h2>🖥️ Экран ведущего</h2><p>Живых: <b>${{d.players.filter(p=>p.alive).length}}</b> • Мест: <b>${{d.places??'?'}}</b> • Голосов: <b>${{d.votes_count||0}}</b></p><p class=muted>Все раскрытые карточки обновляются автоматически.</p></div>` }}
function render(d){{ if(d.error){{document.getElementById('app').innerHTML=`<div class=panel>Ошибка: ${{esc(d.error)}}</div>`;return;}} if(localStorage.getItem('bunker_theme')) setTheme(localStorage.getItem('bunker_theme'));
let vote = d.can_vote ? `<div class=panel><h2>🗳️ Голосование</h2>${{d.players.filter(p=>p.alive && (!d.me || p.id!==d.me.id)).map(p=>`<div class=vote-card><div>👤 <b>${{esc(p.name)}}</b><br><span class=muted>${{esc(p.card?.['Профессия']||'Профессия скрыта')}}</span></div><button class=danger onclick="api('vote',{{target_id:'${{p.id}}'}})">Голосовать</button></div>`).join('')}}</div>` : '';
let players = `<div class=panel><h2>👥 Карточки игроков</h2><p class=muted>Если игрок ничего не раскрыл — будет написано «Не раскрывал».</p><div class=cards>${{d.players.map(publicPlayerCard).join('')}}</div></div>`;
let histItems=(d.history||[]).slice(-40).reverse(); let hist = `<div class=panel history><h2>📜 Replay / История</h2>${{histItems.map(x=>`<p>${{esc(x)}}</p>`).join('') || '<p class=muted>Событий пока нет.</p>'}}</div>`;
let event = d.current_event ? `<div class=panel><h2>⚠️ Событие</h2><p>${{esc(d.current_event)}}</p></div>` : '';
let stats = d.me?.stats ? `<div class=panel><h2>🏆 Профиль</h2><p>Игр: <b>${{d.me.stats.games}}</b></p><p>Побед: <b>${{d.me.stats.wins}}</b></p><p>Поражений: <b>${{d.me.stats.losses}}</b></p><p>Выживаемость: <b>${{d.me.stats.winrate}}%</b></p></div>` : '';
let special = d.me ? `<div class=panel><h2>🃏 Спецкарта</h2><p>${{esc(d.me.card['Спецкарта'])}}</p><button class=good onclick="api('special')" ${{d.me.special_used?'disabled':''}}>${{d.me.special_used?'Уже использована':'Использовать'}}</button></div>` : '';
document.getElementById('app').innerHTML=`<div class=grid><main><div class="panel cat"><h2>${{esc(d.catastrophe.title||'Ожидание старта')}}</h2><p>${{esc(d.catastrophe.desc||'')}}</p><div class=stat><span>Статус: <b>${{esc(d.status)}}</b></span><span>Игроков: <b>${{d.players.length}}/${{d.max_players}}</b></span><span>Мест: <b>${{d.places??'?'}}</b></span><span>Шанс: <b>${{d.survival_rate?Math.round(d.survival_rate*100)+'%':'?'}}</b></span><span>Voice: <b>${{d.voice.online}}/${{d.voice.allowed}}</b></span></div><p class=muted>Проблема бункера: ${{esc(d.bunker_problem||'будет выбрана при старте')}}</p><div class=timer id=timer>${{tleft(d.round_ends_at)}}</div></div>${{presenterPanel(d)}}${{players}}${{myCard(d)}}${{vote}}</main><aside>${{adminPanel(d)}}${{event}}${{special}}${{stats}}${{themePanel()}}${{hist}}</aside></div>`; }}
load(); setInterval(load, 3000); setInterval(updateClock, 1000);
</script></body></html>"""
        return web.Response(text=html, content_type="text/html")

    def voice_status(self, game: GameState) -> dict[str, Any]:
        guild = self.bot.get_guild(game.guild_id)
        online = 0
        if guild and game.voice_channel_id:
            vc = guild.get_channel(game.voice_channel_id)
            if isinstance(vc, discord.VoiceChannel):
                ids = {m.id for m in vc.members}
                online = sum(1 for p in game.players.values() if p.id in ids)
        return {"online": online, "allowed": len(game.players)}

    def user_stats(self, user_id: int) -> dict[str, Any]:
        rec = read_stats().get(str(user_id), {"games": 0, "wins": 0, "losses": 0})
        games = int(rec.get("games", 0))
        wins = int(rec.get("wins", 0))
        return {"games": games, "wins": wins, "losses": int(rec.get("losses", 0)), "winrate": round((wins / games) * 100) if games else 0}

    async def _send_channel_notice(self, game: GameState, text: str = "", embed: discord.Embed | None = None):
        ch = self.bot.get_channel(game.channel_id)
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(content=text or None, embed=embed)
            except Exception:
                pass

    async def web_api_game(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        ended = game.status == "ended"
        players = []
        for p in game.players.values():
            players.append({
                "id": str(p.id), "name": p.name, "alive": p.alive,
                "revealed_keys": list(p.revealed),
                "revealed": [self._field_map_ru().get(k, k) for k in p.revealed],
                "card": self._public_player_card(p, ended=ended),
            })
        data = {
            "id": game.id, "status": game.status, "max_players": game.max_players, "places": game.places,
            "survival_rate": game.survival_rate, "bunker_problem": game.bunker_problem,
            "catastrophe": {"title": game.catastrophe_title, "desc": game.catastrophe_desc},
            "players": players, "can_vote": bool(me and me.alive and game.status == "voting"),
            "votes_count": len(game.votes), "history": game.history, "round_ends_at": game.round_ends_at,
            "current_event": game.current_event, "voice": self.voice_status(game),
            "is_host": self._is_web_host(game, me), "me": None,
        }
        if me:
            data["me"] = {"id": str(me.id), "name": me.name, "alive": me.alive, "revealed_keys": list(me.revealed), "card": {
                "Профессия": me.card.get("profession"), "Возраст": me.card.get("age"), "Здоровье": me.card.get("health"),
                "Хобби": me.card.get("hobby"), "Фобия": me.card.get("phobia"),
                "Багаж": me.card.get("baggage", me.card.get("item")), "Рюкзак": me.card.get("backpack"),
                "Навык": me.card.get("skill"), "Факт": me.card.get("fact"), "Спецкарта": me.card.get("special_card"),
                "Доп. профессия": me.card.get("extra_profession"), "Доп. хобби": me.card.get("extra_hobby"),
                "Доп. факт": me.card.get("extra_fact"), "Доп. багаж": me.card.get("extra_baggage"), "Доп. рюкзак": me.card.get("extra_backpack"),
            }, "special_used": me.special_used, "stats": self.user_stats(me.id)}
        return web.json_response(data)

    async def web_api_reveal(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        if not me or not me.alive or game.status == "ended":
            return web.json_response({"error": "cant_reveal"}, status=403)
        body = await request.json()
        field_name = str(body.get("field", ""))
        valid = {k for k, _ in ROUND_FIELDS} | {"age"}
        if field_name not in valid:
            return web.json_response({"error": "bad_field"}, status=400)
        if field_name not in me.revealed:
            me.revealed.append(field_name)
            add_history(game, f"{me.name} раскрыл: {self._field_map_ru().get(field_name, field_name)}")
            self.persist()
            await self.refresh_message(game)
            await self._send_channel_notice(game, f"🃏 **{me.name}** раскрыл: **{self._field_map_ru().get(field_name, field_name)}**")
        return web.json_response({"ok": True})

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
        add_history(game, f"{me.name} проголосовал")
        self.persist()
        if len(game.votes) >= len(game.alive_players()):
            asyncio.create_task(self.finish_vote(game.id))
        return web.json_response({"ok": True})

    async def web_api_admin(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        if not self._is_web_host(game, me):
            return web.json_response({"error": "host_only"}, status=403)
        body = await request.json()
        action = str(body.get("action", ""))
        if action == "next_round":
            if game.round_index < len(ROUND_FIELDS) - 1:
                game.round_index += 1
            game.round_ends_at = time.time() + int(self.cfg.get("round_seconds", 180))
            add_history(game, f"Ведущий переключил раунд: {game.current_round()[1]}")
        elif action == "vote":
            game.status = "voting"
            game.votes = {}
            game.round_ends_at = time.time() + 180
            add_history(game, "Ведущий запустил голосование")
            await self._send_channel_notice(game, "🗳️ Голосование запущено на сайте.")
        elif action == "finish_vote":
            await self.finish_vote(game.id)
            return web.json_response({"ok": True})
        elif action == "event":
            title, desc, effect = random.choice(RANDOM_EVENTS)
            if effect == "places_plus" and game.places is not None:
                game.places += 1
            elif effect == "places_minus" and game.places is not None:
                game.places = max(1, game.places - 1)
            elif effect.startswith("reveal_"):
                key = effect.replace("reveal_", "")
                for p in game.alive_players():
                    if key not in p.revealed:
                        p.revealed.append(key)
            game.current_event = f"{title}\n{desc}"
            add_history(game, f"Событие: {title}")
            await self._send_channel_notice(game, embed=discord.Embed(title=title, description=desc, color=0xFEE75C))
        elif action == "end":
            await self.end_game_by_state(game, manual=True)
            return web.json_response({"ok": True})
        else:
            return web.json_response({"error": "bad_action"}, status=400)
        self.persist()
        await self.refresh_message(game)
        return web.json_response({"ok": True})

    async def web_api_special(self, request: web.Request):
        game = self.games.get(request.match_info["game_id"])
        if not game:
            return web.json_response({"error": "game_not_found"}, status=404)
        me = self._player_by_token(game, request.query.get("token"))
        if not me or not me.alive or game.status not in ("started", "voting"):
            return web.json_response({"error": "cant_use_special"}, status=403)
        result = self.apply_special_card(game, me)
        await self._send_channel_notice(game, f"🃏 **{me.name}** использовал спецкарту: {result}")
        await self.refresh_message(game)
        return web.json_response({"ok": True, "result": result})


async def setup(bot: commands.Bot):
    await bot.add_cog(BunkerCog(bot))
