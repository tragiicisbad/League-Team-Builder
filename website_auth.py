"""Discord identity and private website profiles. No Discord tokens are stored."""
import hashlib
import json
import os
import secrets
from urllib.parse import urlencode, urlsplit

import aiohttp
from aiohttp import web
from database import connect, get_player

ROLES = {"Top", "Jungle", "Mid", "Bot", "Support", "Fill"}
COOKIE = "__Host-pcl-session"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class WebsiteAuth:
    def __init__(self, sync_roles=None, join_queue=None, leave_queue=None, queue_status=None, ready_queue=None):
        self.queue_status = queue_status
        self.ready_queue = ready_queue
        self.leave_queue = leave_queue
        self.join_queue = join_queue
        self.sync_roles = sync_roles
        self.origin = os.getenv("WEBSITE_PUBLIC_URL", "").rstrip("/")
        self.client_id = os.getenv("DISCORD_CLIENT_ID", "")
        self.secret = os.getenv("DISCORD_CLIENT_SECRET", "")

    @property
    def configured(self):
        parsed = urlsplit(self.origin)
        return bool(self.client_id and self.secret and parsed.scheme == "https" and
                    parsed.netloc and not parsed.path and not parsed.query and not parsed.fragment)

    def setup(self):
        with connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS website_profiles "
                         "(discord_id TEXT PRIMARY KEY, identity TEXT NOT NULL, preferences TEXT NOT NULL DEFAULT '{}')")
            conn.execute("CREATE TABLE IF NOT EXISTS website_sessions "
                         "(token_hash TEXT PRIMARY KEY, discord_id TEXT NOT NULL, expires TIMESTAMPTZ NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS website_oauth_states "
                         "(token_hash TEXT PRIMARY KEY, expires TIMESTAMPTZ NOT NULL)")

    def routes(self, app):
        app.router.add_get("/auth/discord", self.login)
        app.router.add_get("/auth/discord/callback", self.callback)
        app.router.add_get("/api/profile", self.profile)
        app.router.add_post("/api/profile", self.save)
        app.router.add_post("/api/queue/join", self.queue_join)
        app.router.add_post("/api/queue/leave", self.queue_leave)
        app.router.add_get("/api/queue/me", self.queue_me)
        app.router.add_post("/api/queue/ready", self.queue_ready)
        app.router.add_post("/auth/logout", self.logout)

    def check_origin(self, req):
        if req.headers.get("Origin") != self.origin:
            raise web.HTTPForbidden(text="Invalid request origin")

    def current(self, req):
        token = req.cookies.get(COOKIE, "")
        if not token:
            return None
        with connect() as conn:
            row = conn.execute(
                "SELECT p.discord_id, p.identity, p.preferences FROM website_sessions s "
                "JOIN website_profiles p ON p.discord_id=s.discord_id "
                "WHERE s.token_hash=%s AND s.expires>NOW()", (digest(token),)).fetchone()
        return row

    async def login(self, req):
        if not self.configured:
            raise web.HTTPServiceUnavailable(text="Discord sign-in is not configured yet.")
        state = secrets.token_urlsafe(32)
        with connect() as conn:
            conn.execute("DELETE FROM website_oauth_states WHERE expires<NOW()")
            conn.execute("DELETE FROM website_sessions WHERE expires<NOW()")
            conn.execute("INSERT INTO website_oauth_states VALUES (%s, NOW()+INTERVAL '10 minutes')", (digest(state),))
        response = web.HTTPFound("https://discord.com/oauth2/authorize?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.origin + "/auth/discord/callback",
            "response_type": "code", "scope": "identify", "state": state}))
        response.set_cookie("__Host-pcl-oauth", state, secure=True, httponly=True,
                            samesite="Lax", path="/", max_age=600)
        response.headers["Cache-Control"] = "no-store"
        return response

    async def callback(self, req):
        if not self.configured:
            raise web.HTTPServiceUnavailable()
        state = req.query.get("state", "")
        if not state or not secrets.compare_digest(state, req.cookies.get("__Host-pcl-oauth", "")):
            raise web.HTTPForbidden(text="Sign-in expired. Please try again.")
        with connect() as conn:
            valid = conn.execute("DELETE FROM website_oauth_states WHERE token_hash=%s "
                                 "AND expires>NOW() RETURNING token_hash", (digest(state),)).fetchone()
        if not valid:
            raise web.HTTPForbidden(text="Sign-in expired. Please try again.")
        if req.query.get("error"):
            response = web.HTTPFound(self.origin + "/#home")
            response.del_cookie("__Host-pcl-oauth", path="/", secure=True, httponly=True)
            return response
        code = req.query.get("code")
        if not code:
            raise web.HTTPBadRequest(text="Missing authorization code.")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as client:
                async with client.post("https://discord.com/api/oauth2/token", data={
                    "client_id": self.client_id, "client_secret": self.secret,
                    "grant_type": "authorization_code", "code": code,
                    "redirect_uri": self.origin + "/auth/discord/callback"}) as response:
                    if response.status != 200:
                        raise web.HTTPBadGateway(text="Discord sign-in failed. Please try again.")
                    token = (await response.json())["access_token"]
                async with client.get("https://discord.com/api/users/@me",
                                      headers={"Authorization": "Bearer " + token}) as response:
                    if response.status != 200:
                        raise web.HTTPBadGateway(text="Discord identity could not be verified.")
                    user = await response.json()
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError):
            raise web.HTTPBadGateway(text="Discord is unavailable. Please try again.")
        uid = str(user["id"])
        avatar = user.get("avatar")
        identity = {"name": user.get("global_name") or user["username"],
                    "avatar_url": "https://cdn.discordapp.com/avatars/" + uid + "/" + avatar + ".png?size=128" if avatar else None}
        session = secrets.token_urlsafe(32)
        with connect() as conn:
            conn.execute("INSERT INTO website_profiles (discord_id,identity) VALUES (%s,%s) "
                         "ON CONFLICT (discord_id) DO UPDATE SET identity=EXCLUDED.identity", (uid, json.dumps(identity)))
            conn.execute("INSERT INTO website_sessions VALUES (%s,%s,NOW()+INTERVAL '7 days')", (digest(session), uid))
        response = web.HTTPFound(self.origin + "/#profile")
        response.set_cookie(COOKIE, session, secure=True, httponly=True, samesite="Lax", path="/", max_age=604800)
        response.del_cookie("__Host-pcl-oauth", path="/", secure=True, httponly=True)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    async def profile(self, req):
        row = self.current(req) if self.configured else None
        payload = {"authenticated": bool(row), "login_available": self.configured}
        if row:
            payload.update({"discord_id": row[0], "identity": json.loads(row[1]),
                            "preferences": json.loads(row[2]), "riot_linked": False})
            player = get_player(int(row[0]))
            payload["signup_completed"] = player is not None
            if player:
                payload["preferences"] = {
                    "name": player["name"], "primary": "Bot" if player["primary_role"] == "ADC" else player["primary_role"],
                    "secondary": "Bot" if player["secondary_role"] == "ADC" else player["secondary_role"],
                    "avoided": "Bot" if player.get("avoided_role") == "ADC" else player.get("avoided_role", "None")
                }
                payload["player"] = {key: player[key] for key in ("rank", "rating", "wins", "losses")}
        return web.json_response(payload, headers={"Cache-Control": "no-store"})

    async def save(self, req):
        self.check_origin(req)
        row = self.current(req)
        if not row:
            raise web.HTTPUnauthorized()
        try:
            body = await req.json()
            name = body.get("name", "").strip()
            primary, secondary = body.get("primary"), body.get("secondary")
            avoided = body.get("avoided", "None")
            if avoided not in {"None", "Top", "Jungle", "Mid", "Bot", "Support"}:
                raise ValueError()
            if not name or len(name) > 40 or primary not in ROLES or secondary not in ROLES or primary == secondary:
                raise ValueError()
        except (ValueError, AttributeError, TypeError):
            raise web.HTTPBadRequest(text="Enter a name and two different roles.")
        player = get_player(int(row[0]))
        role_synced = True
        if player is not None:
            if self.sync_roles is None:
                raise web.HTTPServiceUnavailable(text="Discord role syncing is unavailable.")
            role_synced = await self.sync_roles(int(row[0]), primary, secondary, avoided)
        with connect() as conn:
            conn.execute("UPDATE website_profiles SET preferences=%s WHERE discord_id=%s",
                         (json.dumps({"name": name, "primary": primary, "secondary": secondary, "avoided": avoided}), row[0]))
        return web.json_response({"saved": True, "discord_role_synced": role_synced},
                                 headers={"Cache-Control": "no-store"})

    async def queue_join(self, req):
        self.check_origin(req)
        row = self.current(req)
        if not row:
            raise web.HTTPUnauthorized(text="Sign in with Discord first.")
        if self.join_queue is None:
            raise web.HTTPServiceUnavailable(text="Queue joining is unavailable.")
        result = await self.join_queue(int(row[0]))
        return web.json_response({"joined": True, "position": result}, headers={"Cache-Control": "no-store"})

    async def queue_leave(self, req):
        self.check_origin(req)
        row = self.current(req)
        if not row:
            raise web.HTTPUnauthorized(text="Sign in with Discord first.")
        if self.leave_queue is None:
            raise web.HTTPServiceUnavailable(text="Queue leaving is unavailable.")
        await self.leave_queue(int(row[0]))
        return web.json_response({"left": True}, headers={"Cache-Control": "no-store"})

    async def queue_me(self, req):
        row = self.current(req)
        if not row:
            raise web.HTTPUnauthorized(text="Sign in with Discord first.")
        if self.queue_status is None:
            raise web.HTTPServiceUnavailable()
        return web.json_response(self.queue_status(int(row[0])), headers={"Cache-Control":"no-store"})

    async def queue_ready(self, req):
        self.check_origin(req)
        row = self.current(req)
        if not row:
            raise web.HTTPUnauthorized()
        if self.ready_queue is None:
            raise web.HTTPServiceUnavailable()
        await self.ready_queue(int(row[0]))
        return web.json_response({"ready":True}, headers={"Cache-Control":"no-store"})

    async def logout(self, req):
        self.check_origin(req)
        token = req.cookies.get(COOKIE, "")
        if token:
            with connect() as conn:
                conn.execute("DELETE FROM website_sessions WHERE token_hash=%s", (digest(token),))
        response = web.json_response({"signed_out": True}, headers={"Cache-Control": "no-store"})
        response.del_cookie(COOKIE, path="/", secure=True, httponly=True)
        return response
