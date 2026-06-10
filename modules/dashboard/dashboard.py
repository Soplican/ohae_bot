# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from aiohttp import web
from discord.ext import commands

# =========================
# Paths / JSON helpers
# =========================
def _here() -> str:
    return os.path.dirname(__file__)

def _web_dir() -> str:
    return os.path.join(_here(), "web")

def _module_dir(module: str) -> str:
    return os.path.abspath(os.path.join(_here(), "..", module))

def _read_json(path: str, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _module_config_path(module: str, guild_id: int | None) -> tuple[str, bool]:
    """
    Returns (path, is_global)
    Per-guild: modules/<module>/configs/<guild>.json
    Global:   modules/<module>/configs/global.json
    """
    module = (module or "").strip()
    if module == "discohook_local":
        return (os.path.join(_module_dir(module), "configs", "global.json"), True)

    if guild_id is None:
        return (os.path.join(_module_dir(module), "configs", "global.json"), True)

    return (os.path.join(_module_dir(module), "configs", f"{guild_id}.json"), False)

def _module_default_path(module: str) -> str | None:
    if module == "welcome":
        return os.path.join(_module_dir("welcome"), "welcome_config.json")
    if module == "infoaudit":
        return os.path.join(_module_dir("infoaudit"), "config.json")
    return None


# =========================
# Route registration
# =========================
def register_routes(app: web.Application, bot: commands.Bot):
    """
    Called by discohook_local BEFORE runner.setup() so router isn't frozen.
    """
    web_dir = _web_dir()

    # UI
    async def handle_index(request: web.Request):
        return web.FileResponse(os.path.join(web_dir, "index.html"))

    app.router.add_get("/dashboard", handle_index)
    app.router.add_static("/dashboard_static/", path=web_dir, show_index=False)

    # favicon (avoid 404 spam)
    async def handle_favicon(request: web.Request):
        ico = os.path.join(web_dir, "favicon.ico")
        if os.path.exists(ico):
            return web.FileResponse(ico)
        raise web.HTTPNotFound()

    app.router.add_get("/favicon.ico", handle_favicon)

    # API: meta
    async def api_meta(request: web.Request):
        bot_user = getattr(bot, "user", None)
        name = "Bot"
        avatar = None
        bot_id = None
        if bot_user is not None:
            try:
                name = bot_user.name
            except Exception:
                pass
            try:
                bot_id = str(bot_user.id)
            except Exception:
                bot_id = None
            try:
                avatar = bot_user.display_avatar.url if bot_user.display_avatar else None
            except Exception:
                avatar = None
        return web.json_response({"bot": {"id": bot_id, "name": name, "avatar_url": avatar}})

    app.router.add_get("/dashboard_api/meta", api_meta)

    # API: guilds
    async def api_guilds(request: web.Request):
        items = []
        for g in bot.guilds:
            icon = None
            try:
                icon = g.icon.url if g.icon else None
            except Exception:
                icon = None
            items.append({"id": str(g.id), "name": g.name, "icon_url": icon})
        items.sort(key=lambda x: x["name"].lower())
        return web.json_response({"guilds": items})

    # API: channels (text)
    async def api_channels(request: web.Request):
        gid = int(request.match_info["guild_id"])
        guild = bot.get_guild(gid)
        if guild is None:
            return web.json_response({"error": "guild_not_found"}, status=404)

        cats = []
        none_cat = {"id": None, "name": "Без категории", "channels": []}
        for ch in guild.text_channels:
            item = {"id": str(ch.id), "name": ch.name}
            if ch.category is None:
                none_cat["channels"].append(item)

        cat_map = {}
        for cat in guild.categories:
            cat_map[cat.id] = {"id": str(cat.id), "name": cat.name, "channels": []}

        for ch in guild.text_channels:
            if ch.category is not None and ch.category.id in cat_map:
                cat_map[ch.category.id]["channels"].append({"id": str(ch.id), "name": ch.name})

        none_cat["channels"].sort(key=lambda x: x["name"].lower())
        cats_list = list(cat_map.values())
        for c in cats_list:
            c["channels"].sort(key=lambda x: x["name"].lower())
        cats_list.sort(key=lambda x: x["name"].lower())

        if none_cat["channels"]:
            cats.append(none_cat)
        cats.extend(cats_list)
        return web.json_response({"categories": cats})

    # API: roles
    async def api_roles(request: web.Request):
        gid = int(request.match_info["guild_id"])
        guild = bot.get_guild(gid)
        if guild is None:
            return web.json_response({"error": "guild_not_found"}, status=404)

        roles = []
        for r in guild.roles:
            if r.is_default():
                continue
            roles.append({"id": str(r.id), "name": r.name, "color": r.color.value})
        roles.sort(key=lambda x: x["name"].lower())
        return web.json_response({"roles": roles})

    app.router.add_get("/dashboard_api/guilds", api_guilds)
    app.router.add_get("/dashboard_api/guilds/{guild_id}/channels", api_channels)
    app.router.add_get("/dashboard_api/guilds/{guild_id}/roles", api_roles)

    # API: modules list (only real extensions)
    async def api_modules(request: web.Request):
        modules_path = os.path.abspath(os.path.join(_here(), ".."))
        mods = []
        for name in os.listdir(modules_path):
            p = os.path.join(modules_path, name)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, f"{name}.py")):
                mods.append(name)
        mods.sort()
        return web.json_response({"modules": mods})

    app.router.add_get("/dashboard_api/modules", api_modules)

    # API: get/save config
    async def api_get_config(request: web.Request):
        module = (request.query.get("module") or "").strip()
        guild_id = request.query.get("guild_id")
        gid = int(guild_id) if guild_id and str(guild_id).isdigit() else None

        if not module:
            return web.json_response({"error": "module_required"}, status=400)

        path, is_global = _module_config_path(module, gid)
        data = _read_json(path, default=None)
        source = "custom" if data is not None and os.path.exists(path) else "default"
        if data is None:
            data = {}

        # fallback defaults for known modules
        if (not os.path.exists(path)) and (module in ("welcome", "infoaudit")):
            dp = _module_default_path(module)
            if dp and os.path.exists(dp):
                data = _read_json(dp, default={})
                source = "default"

        # discohook_local: default from bot config if no override
        if module == "discohook_local" and not os.path.exists(path):
            try:
                from modules.discohook_local.discohook_local import _read_bot_config, _get_cfg  # type: ignore
                cfg = _get_cfg(_read_bot_config(bot))
                data = cfg if isinstance(cfg, dict) else {}
                source = "bot_config"
            except Exception:
                data = {}
                source = "empty"

        return web.json_response({
            "module": module,
            "guild_id": str(gid) if gid else None,
            "is_global": is_global,
            "source": source,
            "data": data
        })

    async def api_save_config(request: web.Request):
        body = await request.json()
        module = (body.get("module") or "").strip()
        guild_id = body.get("guild_id")
        gid = int(guild_id) if isinstance(guild_id, (int, str)) and str(guild_id).isdigit() else None
        data = body.get("data")

        if not module or not isinstance(data, dict):
            return web.json_response({"error": "bad_request"}, status=400)

        path, is_global = _module_config_path(module, gid)

        # minimal defaults so modules don't crash
        if module == "welcome":
            data.setdefault("enabled", True)
            data.setdefault("rows", [])
        if module == "infoaudit":
            data.setdefault("panel", {})
            data.setdefault("logs", {})
            data.setdefault("nickname", {})
        if module == "souz":
            data.setdefault("enabled", True)
            data.setdefault("main_guild_id", 0)
            data.setdefault("log_channel_id", 0)
            data.setdefault("main_manage", {})
            data.setdefault("whitelist", {"user_ids": [], "role_ids": []})
            data.setdefault("sources", [])
        if module == "requests":
            data.setdefault("enabled", True)
            data.setdefault("panel", {})
            data.setdefault("types", [])
            data.setdefault("storage", {})

        _write_json(path, data)
        return web.json_response({"ok": True, "is_global": is_global})

    # API: requests -> publish panel (from dashboard button)
    async def api_requests_panel_publish(request: web.Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        guild_id = body.get("guild_id")
        panel_id = body.get("panel_id")
        try:
            gid = int(str(guild_id))
        except Exception:
            return web.json_response({"ok": False, "error": "bad_guild_id"}, status=400)

        guild = bot.get_guild(gid)
        if guild is None:
            return web.json_response({"ok": False, "error": "guild_not_found"}, status=404)

        cog = bot.get_cog("RequestsCog")
        if cog is None or not hasattr(cog, "publish_panel"):
            return web.json_response({"ok": False, "error": "requests_cog_not_loaded"}, status=400)

        try:
            ok, code = await cog.publish_panel(guild, panel_id=panel_id)
        except Exception as e:
            return web.json_response({"ok": False, "error": "exception", "detail": str(e)}, status=500)

        if ok:
            return web.json_response({"ok": True})
        return web.json_response({"ok": False, "error": code}, status=400)

    app.router.add_post("/dashboard_api/requests/panel/publish", api_requests_panel_publish)

    app.router.add_get("/dashboard_api/config/get", api_get_config)
    app.router.add_post("/dashboard_api/config/save", api_save_config)


# =========================
# discord.py extension setup
# =========================
class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    # routes are registered from discohook_local via register_routes()
    await bot.add_cog(Dashboard(bot))