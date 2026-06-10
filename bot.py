import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from discord.ext import commands

BASE_DIR = Path(__file__).parent
MODULES_DIR = BASE_DIR / "modules"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "config.json"


# -------------------------
# Config
# -------------------------
def load_main_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json not found рядом с bot.py")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


# -------------------------
# Logging
# -------------------------
def make_rotating_handler(log_file: Path) -> RotatingFileHandler:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,  # 2MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"))
    return handler


def setup_bot_logger() -> logging.Logger:
    logger = logging.getLogger("Phantom_Bot")
    logger.setLevel(logging.INFO)

    # Не плодим handlers при перезапуске
    if logger.handlers:
        return logger

    logger.addHandler(make_rotating_handler(LOGS_DIR / "bot" / "bot.log"))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(console)

    logger.propagate = False
    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Гарантирует, что logger "Phantom_Bot.modules.<name>" пишет в logs/modules/<name>/<name>.log
    """
    logger = logging.getLogger(f"Phantom_Bot.modules.{module_name}")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    logger.addHandler(make_rotating_handler(LOGS_DIR / "modules" / module_name / f"{module_name}.log"))
    logger.propagate = False
    return logger


# -------------------------
# Module Loader
# -------------------------
def discover_modules() -> list[str]:
    """
    Ищем модули по схеме:
      modules/<name>/<name>.py
    """
    if not MODULES_DIR.exists():
        return []

    out: list[str] = []
    for p in MODULES_DIR.iterdir():
        if p.is_dir() and (p / f"{p.name}.py").exists():
            out.append(p.name)

    return sorted(out)


def extension_path(module_name: str) -> str:
    # modules.welcome.welcome
    return f"modules.{module_name}.{module_name}"


async def load_modules(bot: commands.Bot, enabled: list[str] | None, log: logging.Logger) -> dict:
    all_mods = discover_modules()
    target = all_mods if enabled is None else [m for m in all_mods if m in enabled]

    results: dict[str, tuple[bool, str | None]] = {}
    for name in target:
        ext = extension_path(name)
        try:
            # Подготовим логгер модуля, чтобы он сразу писал в файл
            get_module_logger(name)

            await bot.load_extension(ext)
            results[name] = (True, None)
            log.info(f"[MODULE] {name}: loaded")
        except Exception as e:
            results[name] = (False, str(e))
            log.error(f"[MODULE] {name}: failed -> {e}")
    return results


# -------------------------
# Intents
# -------------------------
def build_intents(cfg: dict) -> discord.Intents:
    intents = discord.Intents.default()
    icfg = cfg.get("intents", {})

    if icfg.get("members", False):
        intents.members = True
    if icfg.get("message_content", False):
        intents.message_content = True

    return intents


# -------------------------
# Slash command sync helper
# -------------------------
async def sync_app_commands_all_guilds(bot: commands.Bot, log: logging.Logger):
    """Синхронизирует слеш-команды на всех гильдиях, где есть бот."""
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            log.info(f"Синхронизированы команды для гильдии {guild.name} (ID: {guild.id})")
        except Exception as e:
            log.error(f"Ошибка синхронизации для гильдии {guild.name}: {e}")


# -------------------------
# Main bot function
# -------------------------
async def main():
    cfg = load_main_config()
    log = setup_bot_logger()

    intents = build_intents(cfg)
    bot = commands.Bot(command_prefix=cfg.get("prefix", "!"), intents=intents)

    # Храним результаты загрузки
    bot.module_status: dict[str, tuple[bool, str | None]] = {}

    def is_admin(ctx: commands.Context) -> bool:
        perms = getattr(ctx.author, "guild_permissions", None)
        return bool(perms and perms.administrator)

    @bot.event
    async def on_ready():
        log.info(f"Logged in as {bot.user} (id={bot.user.id})")

        # Автосинк slash-команд на всех серверах, где есть бот
        if not getattr(bot, "_appcmds_synced", False):
            try:
                await sync_app_commands_all_guilds(bot, log)
                bot._appcmds_synced = True
            except Exception as e:
                log.error(f"Ошибка автосинка команд: {e}")

    # -------------------------
    # Command: sync app commands (slash) on all guilds
    # -------------------------
    @bot.command(name="synccommands")
    async def synccommands_cmd(ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")
        await ctx.send("🔄 Синхронизирую slash-команды на всех серверах, где есть бот…")
        try:
            await sync_app_commands_all_guilds(bot, log)
            await ctx.send("✅ Готово: команды синхронизированы.")
        except Exception as e:
            log.error(f"[APP COMMANDS] manual sync failed -> {e}")
            await ctx.send(f"❌ Ошибка синка: `{e}`")

    # -------------------------
    # Commands: modules list
    # -------------------------
    @bot.command(name="modules")
    async def modules_cmd(ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")
        all_mods = discover_modules()
        if not all_mods:
            return await ctx.send("Модули не найдены в папке `modules/`.")

        lines = []
        for m in all_mods:
            ok, err = bot.module_status.get(m, (False, "not loaded"))
            lines.append(f"✅ {m}" if ok else f"❌ {m} — {err}")
        await ctx.send("**Модули:**\n" + "\n".join(lines))


    @bot.command(name="version")
    async def version_cmd(ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")
        await ctx.send(f"📦 discord.py версия: `{discord.__version__}`")

    # -------------------------
    # Commands: reload / load / unload
    # -------------------------
    @bot.command()
    async def reload(ctx: commands.Context, module_name: str):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")

        ext = extension_path(module_name)
        try:
            get_module_logger(module_name)

            if ext in bot.extensions:
                await bot.unload_extension(ext)

            await bot.load_extension(ext)
            bot.module_status[module_name] = (True, None)
            log.info(f"[MODULE] {module_name}: reloaded")
            await ctx.send(f"✅ Перезагружен: `{module_name}`")
        except Exception as e:
            bot.module_status[module_name] = (False, str(e))
            log.error(f"[MODULE] {module_name}: reload failed -> {e}")
            await ctx.send(f"❌ Ошибка: `{e}`")

    @bot.command()
    async def load(ctx: commands.Context, module_name: str):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")

        ext = extension_path(module_name)
        try:
            get_module_logger(module_name)

            await bot.load_extension(ext)
            bot.module_status[module_name] = (True, None)
            log.info(f"[MODULE] {module_name}: loaded via command")
            await ctx.send(f"✅ Загружен: `{module_name}`")
        except Exception as e:
            bot.module_status[module_name] = (False, str(e))
            log.error(f"[MODULE] {module_name}: load failed -> {e}")
            await ctx.send(f"❌ Ошибка: `{e}`")

    @bot.command()
    async def unload(ctx: commands.Context, module_name: str):
        if not is_admin(ctx):
            return await ctx.send("Нет прав.")

        ext = extension_path(module_name)
        try:
            await bot.unload_extension(ext)
            bot.module_status[module_name] = (False, "unloaded")
            log.info(f"[MODULE] {module_name}: unloaded via command")
            await ctx.send(f"✅ Выгружен: `{module_name}`")
        except Exception as e:
            bot.module_status[module_name] = (False, str(e))
            log.error(f"[MODULE] {module_name}: unload failed -> {e}")
            await ctx.send(f"❌ Ошибка: `{e}`")
    
    # -------------------------
    # Command: create module skeleton
    # -------------------------
    @bot.command()
    async def createmodule(ctx: commands.Context, module_name: str):
        if not is_admin(ctx):
            await ctx.send("Нет прав.")
            return

        # Защита от пробелов, дефисов и т.п.
        if not module_name.isidentifier():
            await ctx.send("❌ Имя модуля должно быть как в Python: буквы/цифры/_ и не начинаться с цифры.")
            return

        mod_dir = MODULES_DIR / module_name
        py_path = mod_dir / f"{module_name}.py"
        init_path = mod_dir / "__init__.py"
        cfg_path = mod_dir / f"{module_name}_config.json"

        if mod_dir.exists():
            await ctx.send("❌ Папка модуля уже существует.")
            return

        mod_dir.mkdir(parents=True, exist_ok=True)
        init_path.write_text("", encoding="utf-8")

        cfg_path.write_text(
            "{\n"
            '  "enabled": true,\n'
            f'  "example": "hello from {module_name}"\n'
            "}\n",
            encoding="utf-8",
        )

        class_name = "".join(part.capitalize() for part in module_name.split("_")) or "Module"

        template = f"""import logging
import json
from pathlib import Path

import discord
from discord.ext import commands

MODULE_NAME = "{module_name}"
log = logging.getLogger("Phantom_Bot.modules.{module_name}")

CFG_PATH = Path("modules") / MODULE_NAME / f"{{MODULE_NAME}}_config.json"

def load_cfg() -> dict:
    if not CFG_PATH.exists():
        raise FileNotFoundError(f"{{CFG_PATH}} not found")
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))

class {class_name}Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        cfg = load_cfg()
        log.info("Module init OK, enabled=%s", cfg.get("enabled", True))

    @commands.command()
    async def {module_name}_ping(self, ctx: commands.Context):
        cfg = load_cfg()
        await ctx.send(f"✅ {module_name} работает. example={{cfg.get('example')}}")

async def setup(bot: commands.Bot):
    await bot.add_cog({class_name}Cog(bot))
"""
        py_path.write_text(template, encoding="utf-8")

        await ctx.send(
            f"✅ Модуль `{module_name}` создан.\n"
            f"Файл: `modules/{module_name}/{module_name}.py`\n"
            f"Теперь можно: `!load {module_name}`"
        )

    # -------------------------
    # Auto-load enabled modules from config
    # -------------------------
    enabled = cfg.get("modules_enabled")
    bot.module_status = await load_modules(bot, enabled, log)

    await bot.start(cfg["token"])


if __name__ == "__main__":
    asyncio.run(main())