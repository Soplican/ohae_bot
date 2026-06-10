# -*- coding: utf-8 -*-
"""
discohook_local - Local Discohook-like UI (Visual + JSON + Preview)
- Sends messages as bot (channel_id) or via webhook (webhook_url)
- Hosts a small local website (index.html + app.js + style.css)
- Авторизация через Discord OAuth2 (только для администраторов сервера)
- При отправке проверяется, что пользователь админ на выбранном сервере
"""
from __future__ import annotations

import json
import pathlib
import traceback
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import web
from aiohttp_session import setup as setup_session, get_session, new_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

import discord
from discord.ext import commands


def _safe_int(v: Any) -> Optional[int]:
    try:
        n = int(str(v).strip())
        return n
    except Exception:
        return None


def _load_config(bot: commands.Bot) -> Dict[str, Any]:
    """Загружает конфиг из разных мест."""
    cfg = getattr(bot, "config", None)
    if isinstance(cfg, dict):
        return cfg
    p = getattr(bot, "config_path", None)
    if p:
        try:
            return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except Exception:
            pass
    for candidate in ("config.json", "settings.json"):
        try:
            path = pathlib.Path(candidate)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _get_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("discohook_local", {}) if isinstance(cfg, dict) else {}


def _make_embed(d: Dict[str, Any]) -> Optional[discord.Embed]:
    """Создаёт embed из словаря с проверкой лимитов Discord. Возвращает None при ошибке."""
    try:
        # --- Цвет ---
        color_val = d.get("color")
        color: Optional[discord.Color] = None
        if isinstance(color_val, int):
            color = discord.Color(color_val)
        elif isinstance(color_val, str):
            s = color_val.strip()
            if s.startswith("#"):
                s = s[1:]
            try:
                color = discord.Color(int(s, 16))
            except Exception:
                color = None

        # --- Ограничения длин (обрезка с многоточием) ---
        def truncate(text: Optional[str], limit: int) -> Optional[str]:
            if not text:
                return text
            if len(text) > limit:
                return text[: limit - 3] + "..."
            return text

        title = truncate(d.get("title"), 256)
        description = truncate(d.get("description"), 4096)
        url = d.get("url")

        e = discord.Embed(
            title=title,
            description=description,
            url=url,
            color=color or discord.Color.blurple(),
        )

        # --- Timestamp ---
        ts = d.get("timestamp")
        if ts:
            try:
                if isinstance(ts, str):
                    if ts.endswith("Z"):
                        ts = ts[:-1] + "+00:00"
                    dt = datetime.fromisoformat(ts)
                    e.timestamp = dt
            except Exception:
                pass

        # --- Author ---
        a = d.get("author") or {}
        if isinstance(a, dict) and a.get("name"):
            author_name = truncate(a.get("name"), 256)
            e.set_author(
                name=author_name,
                url=a.get("url"),
                icon_url=a.get("icon_url"),
            )

        # --- Thumbnail ---
        th = (d.get("thumbnail") or {}).get("url")
        if isinstance(th, str) and th.strip():
            e.set_thumbnail(url=th.strip())

        # --- Image ---
        im = (d.get("image") or {}).get("url")
        if isinstance(im, str) and im.strip():
            e.set_image(url=im.strip())

        # --- Fields ---
        fields = d.get("fields")
        if isinstance(fields, list):
            for f in fields[:25]:
                if not isinstance(f, dict):
                    continue
                name = truncate(f.get("name"), 256) or "\u200b"
                value = truncate(f.get("value"), 1024) or "\u200b"
                inline_raw = f.get("inline")
                if isinstance(inline_raw, str):
                    inline = inline_raw.lower() == "true"
                else:
                    inline = bool(inline_raw)
                e.add_field(name=name, value=value, inline=inline)

        # --- Footer ---
        ft = d.get("footer") or {}
        if isinstance(ft, dict) and ft.get("text"):
            footer_text = truncate(ft.get("text"), 2048)
            e.set_footer(text=footer_text, icon_url=ft.get("icon_url"))

        return e
    except Exception as err:
        print(f"[DiscohookLocal] Ошибка создания embed: {err}")
        traceback.print_exc()
        return None


def _make_view(components: Any) -> Optional[discord.ui.View]:
    if not isinstance(components, list) or not components:
        return None

    view = discord.ui.View(timeout=None)
    rows_used = 0
    for row in components[:5]:
        if not isinstance(row, dict):
            continue
        if int(row.get("type", 1)) != 1:
            continue
        btns = row.get("components")
        if not isinstance(btns, list) or not btns:
            continue

        cols_used = 0
        for b in btns[:5]:
            if not isinstance(b, dict):
                continue
            if int(b.get("type", 2)) != 2:
                continue

            style = int(b.get("style", 2))
            label = str(b.get("label", "Button"))
            disabled = bool(b.get("disabled", False))

            if style == 5:
                url = b.get("url")
                if not isinstance(url, str) or not url:
                    continue
                item = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.link,
                    url=url,
                    disabled=disabled,
                    row=rows_used
                )
                view.add_item(item)
            else:
                custom_id = b.get("custom_id")
                if not isinstance(custom_id, str) or not custom_id:
                    custom_id = f"dl_{rows_used}_{cols_used}_{abs(hash(label)) % 999999}"
                style_map = {
                    1: discord.ButtonStyle.primary,
                    2: discord.ButtonStyle.secondary,
                    3: discord.ButtonStyle.success,
                    4: discord.ButtonStyle.danger,
                }
                item = discord.ui.Button(
                    label=label,
                    style=style_map.get(style, discord.ButtonStyle.secondary),
                    custom_id=custom_id,
                    disabled=disabled,
                    row=rows_used
                )
                view.add_item(item)

            cols_used += 1
        rows_used += 1

    return view if view.children else None


class DiscohookLocal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        cfg_all = _load_config(bot)
        self.cfg = _get_cfg(cfg_all)

        self.enabled: bool = bool(self.cfg.get("enabled", True))
        self.host: str = str(self.cfg.get("host", "127.0.0.1"))
        self.port: int = int(self.cfg.get("port", 8787))

        # OAuth2 параметры
        self.oauth2_client_id = str(self.cfg.get("oauth2_client_id", ""))
        self.oauth2_client_secret = str(self.cfg.get("oauth2_client_secret", ""))
        self.oauth2_redirect_uri = str(self.cfg.get("oauth2_redirect_uri", "http://127.0.0.1:8787/callback"))
        self.session_secret = str(self.cfg.get("session_secret", secrets.token_hex(32)))
        self.required_guild_id = self.cfg.get("required_guild_id")

        self.default_channel_id: int = int(self.cfg.get("default_channel_id", 0) or 0)
        self.allow_webhook_send: bool = bool(self.cfg.get("allow_webhook_send", True))
        self.allow_bot_send: bool = bool(self.cfg.get("allow_bot_send", True))

        self.http_session: Optional[aiohttp.ClientSession] = None
        self.web_app: Optional[web.Application] = None
        self.web_runner: Optional[web.AppRunner] = None
        self.web_site: Optional[web.TCPSite] = None
        self.web_dir = pathlib.Path(__file__).parent / "web"

    async def cog_load(self):
        if self.http_session is None:
            self.http_session = aiohttp.ClientSession()
        if self.enabled:
            await self.start_web()

    async def cog_unload(self):
        await self.stop_web()
        if self.http_session is not None:
            await self.http_session.close()
            self.http_session = None

    async def start_web(self):
        if self.web_runner:
            return

        self.web_app = web.Application()
        import base64
        from cryptography import fernet
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        setup_session(self.web_app, EncryptedCookieStorage(secret_key))

        # Публичные маршруты
        self.web_app.router.add_get("/login", self.handle_login)
        self.web_app.router.add_get("/callback", self.handle_callback)
        self.web_app.router.add_get("/logout", self.handle_logout)
        self.web_app.router.add_static("/static/", path=str(self.web_dir), show_index=False)

        # Защищённые маршруты
        self.web_app.router.add_get("/", self.handle_index_auth)
        self.web_app.router.add_get("/api/meta", self.handle_meta_auth)
        self.web_app.router.add_post("/api/send", self.handle_send_auth)
        self.web_app.router.add_get("/api/guilds", self.handle_guilds_auth)
        self.web_app.router.add_get("/api/channels", self.handle_channels_auth)
        self.web_app.router.add_get("/api/user", self.handle_user_auth)

        # Опционально: dashboard
        try:
            from modules.dashboard.dashboard import register_routes as _dash_register
            _dash_register(self.web_app, self.bot)
        except Exception:
            pass

        self.web_runner = web.AppRunner(self.web_app)
        await self.web_runner.setup()
        self.web_site = web.TCPSite(self.web_runner, self.host, self.port)
        await self.web_site.start()
        print(f"[DiscohookLocal] UI запущен на http://{self.host}:{self.port} (требуется авторизация)")

    async def stop_web(self):
        if self.web_site:
            await self.web_site.stop()
            self.web_site = None
        if self.web_runner:
            await self.web_runner.cleanup()
            self.web_runner = None
        self.web_app = None

    async def _check_auth(self, request: web.Request) -> Optional[web.Response]:
        session = await get_session(request)
        if not session or "user_id" not in session:
            if request.path.startswith("/api/"):
                return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
            else:
                return web.HTTPFound("/login")
        return None

    # ---------- Защищённые обёртки ----------
    async def handle_index_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_index(request)

    async def handle_meta_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_meta(request)

    async def handle_send_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_send(request)

    async def handle_guilds_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_guilds(request)

    async def handle_channels_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_channels(request)

    async def handle_user_auth(self, request: web.Request):
        if resp := await self._check_auth(request):
            return resp
        return await self.handle_user(request)

    # ---------- Публичные обработчики ----------
    async def handle_login(self, request: web.Request):
        discord_auth_url = (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={self.oauth2_client_id}"
            "&redirect_uri=" + self.oauth2_redirect_uri +
            "&response_type=code"
            "&scope=identify%20guilds"
        )
        raise web.HTTPFound(discord_auth_url)

    async def handle_callback(self, request: web.Request):
        code = request.query.get("code")
        if not code:
            return web.Response(text="No code provided", status=400)

        token_url = "https://discord.com/api/oauth2/token"
        data = {
            "client_id": self.oauth2_client_id,
            "client_secret": self.oauth2_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.oauth2_redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with self.http_session.post(token_url, data=data, headers=headers) as resp:
            if resp.status != 200:
                return web.Response(text="Failed to get token", status=400)
            token_data = await resp.json()
            access_token = token_data.get("access_token")

        if not access_token:
            return web.Response(text="No access token", status=400)

        headers = {"Authorization": f"Bearer {access_token}"}
        async with self.http_session.get("https://discord.com/api/users/@me", headers=headers) as resp:
            if resp.status != 200:
                return web.Response(text="Failed to get user", status=400)
            user_data = await resp.json()
            user_id = user_data.get("id")
            username = user_data.get("username")

        async with self.http_session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
            if resp.status != 200:
                return web.Response(text="Failed to get guilds", status=400)
            guilds_data = await resp.json()

        # Собираем ID серверов, где пользователь админ и бот присутствует
        bot_guild_ids = {str(g.id) for g in self.bot.guilds}
        admin_guilds = []
        for g in guilds_data:
            if g["id"] not in bot_guild_ids:
                continue
            perms = int(g.get("permissions", "0"))
            if perms & 0x8:
                admin_guilds.append(g["id"])

        if not admin_guilds:
            return web.Response(
                text="У вас нет прав администратора ни на одном сервере, где находится бот.",
                status=403
            )

        session = await new_session(request)
        session["user_id"] = user_id
        session["username"] = username
        session["admin_guilds"] = admin_guilds
        session["access_token"] = access_token

        raise web.HTTPFound("/")

    async def handle_logout(self, request: web.Request):
        session = await get_session(request)
        session.invalidate()
        return web.Response(text="Вы вышли. <a href='/'>Вернуться</a>", content_type="text/html")

    async def handle_user(self, request: web.Request):
        session = await get_session(request)
        return web.json_response({
            "ok": True,
            "user_id": session.get("user_id"),
            "username": session.get("username"),
        })

    async def handle_index(self, request: web.Request):
        index_path = self.web_dir / "index.html"
        if not index_path.exists():
            return web.Response(text="Missing web/index.html", content_type="text/plain", charset="utf-8")
        return web.FileResponse(path=index_path)

    async def handle_meta(self, request: web.Request):
        u = self.bot.user
        if not u:
            return web.json_response({"ok": False})
        return web.json_response({
            "ok": True,
            "bot_name": u.name,
            "bot_avatar": str(u.display_avatar.url) if u.display_avatar else None,
        })

    async def handle_guilds(self, request: web.Request):
        guilds = []
        for g in self.bot.guilds:
            icon_url = str(g.icon.url) if getattr(g, "icon", None) else None
            banner_url = str(g.banner.url) if getattr(g, "banner", None) else None
            guilds.append({"id": str(g.id), "name": g.name, "icon_url": icon_url, "banner_url": banner_url})
        guilds.sort(key=lambda x: x["name"].lower())
        return web.json_response({"ok": True, "guilds": guilds})

    async def handle_channels(self, request: web.Request):
        gid = (request.query.get("guild_id") or "").strip()
        guild_id = _safe_int(gid)
        if not guild_id:
            return web.json_response({"ok": False, "error": "guild_id required"}, status=400)

        g = self.bot.get_guild(guild_id)
        if not g:
            return web.json_response({"ok": False, "error": "guild not found"}, status=404)

        me = g.me
        def can_view(ch: discord.abc.GuildChannel) -> bool:
            try:
                return bool(me and ch.permissions_for(me).view_channel)
            except Exception:
                return True

        groups = []
        cat_channels = {}
        for ch in getattr(g, "text_channels", []):
            if not can_view(ch):
                continue
            cat_id = str(ch.category_id) if ch.category_id else None
            cat_channels.setdefault(cat_id, []).append({"id": str(ch.id), "name": f"#{ch.name}"})

        for k in list(cat_channels.keys()):
            cat_channels[k].sort(key=lambda x: x["name"].lower())

        if None in cat_channels:
            groups.append({"category_id": None, "category_name": "Без категории", "channels": cat_channels[None]})

        cats = [c for c in g.categories if can_view(c)]
        cats.sort(key=lambda c: c.position)
        for c in cats:
            cid = str(c.id)
            if cid in cat_channels and cat_channels[cid]:
                groups.append({"category_id": cid, "category_name": c.name, "channels": cat_channels[cid]})

        return web.json_response({"ok": True, "groups": groups})

    async def handle_send(self, request: web.Request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

        mode = str(data.get("mode", "bot")).lower().strip()
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "payload must be object"}, status=400)

        content = payload.get("content")
        if content is not None and not isinstance(content, str):
            content = str(content)

        embeds_raw = payload.get("embeds") or []
        embeds: List[discord.Embed] = []
        if isinstance(embeds_raw, list):
            for ed in embeds_raw[:10]:
                if isinstance(ed, dict):
                    emb = _make_embed(ed)
                    if emb:
                        embeds.append(emb)

        view = _make_view(payload.get("components"))

        # Если режим вебхука – отправляем без проверки прав
        if mode == "webhook":
            if not self.allow_webhook_send:
                return web.json_response({"ok": False, "error": "Webhook send disabled"}, status=403)

            webhook_url = str(data.get("webhook_url") or "").strip()
            if not webhook_url:
                return web.json_response({"ok": False, "error": "webhook_url is required"}, status=400)

            if self.http_session is None:
                self.http_session = aiohttp.ClientSession()

            try:
                wh = discord.Webhook.from_url(webhook_url, session=self.http_session)
                msg = await wh.send(
                    content=content,
                    embeds=embeds if embeds else None,
                    view=view,
                    wait=True,
                    username=payload.get("username"),
                    avatar_url=payload.get("avatar_url"),
                )
                return web.json_response({"ok": True, "webhook_message_id": getattr(msg, "id", None)})
            except Exception as e:
                return web.json_response({"ok": False, "error": f"Webhook send failed: {e}"}, status=500)

        # Режим бота – требуется проверка прав администратора на сервере
        if not self.allow_bot_send:
            return web.json_response({"ok": False, "error": "Bot send disabled"}, status=403)

        channel_id = _safe_int(data.get("channel_id")) or (self.default_channel_id if self.default_channel_id else None)
        if not channel_id:
            return web.json_response({"ok": False, "error": "channel_id is required for bot mode"}, status=400)

        # Получаем канал и его сервер
        ch = self.bot.get_channel(channel_id)
        if ch is None:
            try:
                ch = await self.bot.fetch_channel(channel_id)
            except:
                return web.json_response({"ok": False, "error": "Channel not found"}, status=404)

        guild = getattr(ch, "guild", None)
        if not guild:
            return web.json_response({"ok": False, "error": "Channel is not in a guild"}, status=400)

        # Проверяем, есть ли у пользователя права администратора на этом сервере
        session = await get_session(request)
        admin_guilds = session.get("admin_guilds", [])
        if str(guild.id) not in admin_guilds:
            return web.json_response({
                "ok": False,
                "error": "You do not have administrator permissions on this server."
            }, status=403)

        # Отправляем
        try:
            sent = await ch.send(content=content, embeds=embeds if embeds else None, view=view)
            return web.json_response({"ok": True, "message_id": getattr(sent, "id", None)})
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Bot send failed: {e}"}, status=500)


async def setup(*args, **kwargs):
    bot = args[0]
    await bot.add_cog(DiscohookLocal(bot))