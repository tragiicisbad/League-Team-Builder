"""NA tournament games, linked accounts, and authenticated result notifications."""

import asyncio
import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote

import aiohttp
from aiohttp import web

from database import connect


class RiotError(Exception):
    pass


def enabled():
    return os.getenv("RIOT_AUTO_RESULTS", "false").lower() == "true"


def setup():
    with connect() as conn:
        conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS public_history BOOLEAN NOT NULL DEFAULT TRUE")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS riot_accounts (
                discord_id BIGINT PRIMARY KEY REFERENCES players(discord_id) ON DELETE CASCADE,
                puuid TEXT NOT NULL UNIQUE, game_name TEXT NOT NULL, tag_line TEXT NOT NULL,
                public_history BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS riot_games (
                code TEXT PRIMARY KEY, token TEXT NOT NULL, snapshot JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', riot_match_id TEXT UNIQUE,
                winner TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE riot_games ADD COLUMN IF NOT EXISTS winner TEXT")
        conn.execute("ALTER TABLE riot_games ADD COLUMN IF NOT EXISTS local_match_id INTEGER")
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS riot_one_pending_game
            ON riot_games ((1)) WHERE status IN ('pending', 'processing', 'needs_review')
        """)


def account(discord_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT puuid, game_name, tag_line, public_history FROM riot_accounts WHERE discord_id=%s",
            (discord_id,)
        ).fetchone()
    if row:
        return dict(zip(("puuid", "game_name", "tag_line", "public_history"), row))


def save_account(discord_id, data, public_history):
    with connect() as conn:
        conn.execute("""
            INSERT INTO riot_accounts (discord_id, puuid, game_name, tag_line, public_history)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (discord_id) DO UPDATE SET puuid=EXCLUDED.puuid,
                game_name=EXCLUDED.game_name, tag_line=EXCLUDED.tag_line,
                public_history=EXCLUDED.public_history
        """, (discord_id, data["puuid"], data["gameName"], data["tagLine"], public_history))


def pending_game():
    with connect() as conn:
        row = conn.execute(
            "SELECT code, token, snapshot, status FROM riot_games "
            "WHERE status IN ('pending', 'processing', 'needs_review') ORDER BY created_at LIMIT 1"
        ).fetchone()
    if row:
        return dict(zip(("code", "token", "snapshot", "status"), row))


def set_status(code, status):
    with connect() as conn:
        conn.execute("UPDATE riot_games SET status=%s WHERE code=%s", (status, code))


def public_data():
    with connect() as conn:
        rows = conn.execute("""
            SELECT p.name, p.rank, p.rating, p.wins, p.losses, p.primary_role
            FROM players p
            WHERE p.public_history ORDER BY p.rating DESC, p.wins DESC, p.name
        """).fetchall()
        roster = conn.execute("SELECT name, public_history FROM players").fetchall()
        games = conn.execute("""
            SELECT blue_team, red_team, winner, date_played FROM matches
            ORDER BY id DESC LIMIT 200
        """).fetchall()
    history = []
    names = {}
    for name, shared in roster:
        names.setdefault(name, []).append(shared)
    for blue, red, winner, date in games:
        teams = {}
        try:
            for side, stored in (("blue", blue), ("red", red)):
                entries = json.loads(stored) if isinstance(stored, str) else stored
                teams[side] = []
                for entry in entries:
                    prefix, separator, name = entry.partition(":")
                    role = prefix.split()[-1] if prefix.split() else ""
                    if not separator or role not in ("Top", "Jungle", "Mid", "ADC", "Bot", "Support"):
                        raise ValueError("Unknown historical player format")
                    name = name.strip()
                    # Legacy records contain names, so ambiguous or renamed accounts need review.
                    if names.get(name) != [True]:
                        raise ValueError("Participant is not unambiguously public")
                    teams[side].append({"name": name, "role": role})
            if len(teams["blue"]) != 5 or len(teams["red"]) != 5:
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        history.append({"winner": winner, "date": str(date).replace(" ", "T"), **teams})
    return {"leaderboard": [dict(zip(("name", "rank", "rating", "wins", "losses", "role"), row))
                            for row in rows], "matches": history[:30]}


async def request(method, path, *, body=None, params=None):
    key = os.getenv("RIOT_API_KEY")
    if not key:
        raise RiotError("RIOT_API_KEY is not configured.")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
        for attempt in range(3):
            async with session.request(
                method, "https://americas.api.riotgames.com" + path,
                headers={"X-Riot-Token": key}, json=body, params=params
            ) as response:
                if response.status == 429:
                    delay = min(max(float(response.headers.get("Retry-After", "10")), 1), 60)
                    await asyncio.sleep(delay)
                    continue
                if response.status == 404:
                    raise RiotError("Riot could not find that account or game.")
                if response.status in (401, 403):
                    raise RiotError("Riot rejected the API key. Check its expiry and Tournament API access.")
                if response.status >= 500 and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if response.status != 200:
                    raise RiotError(f"Riot returned HTTP {response.status}.")
                return await response.json()
    raise RiotError("Riot rate limit reached. Try again later.")


async def lookup(riot_id):
    name, separator, tag = riot_id.strip().rpartition("#")
    if not separator or not name or not tag:
        raise RiotError("Enter your full Riot ID, for example Name#NA1.")
    return await request("GET", f"/riot/account/v1/accounts/by-riot-id/{quote(name, safe='')}/{quote(tag, safe='')}")


async def create_game(snapshot):
    if pending_game():
        raise RiotError("A tournament game is already active.")
    provider = os.getenv("RIOT_PROVIDER_ID")
    if not provider:
        raise RiotError("Register a provider with !riotsetup after configuring RIOT_CALLBACK_URL.")
    players = snapshot["blue"] + snapshot["red"]
    linked = {str(p["discord_id"]): account(p["discord_id"]) for p in players}
    missing = [p["name"] for p in players if not linked[str(p["discord_id"])]]
    if missing:
        raise RiotError("These players need /linkriot first: " + ", ".join(missing))
    snapshot["puuids"] = {uid: a["puuid"] for uid, a in linked.items()}
    tournament = await request("POST", "/lol/tournament/v5/tournaments", body={
        "providerId": int(provider), "name": "Community Customs"
    })
    token = secrets.token_urlsafe(32)
    codes = await request("POST", "/lol/tournament/v5/codes", params={
        "tournamentId": tournament, "count": 1
    }, body={
        "teamSize": 5, "mapType": "SUMMONERS_RIFT", "pickType": "TOURNAMENT_DRAFT",
        "spectatorType": "LOBBYONLY", "allowedParticipants": list(snapshot["puuids"].values()),
        "metadata": json.dumps({"token": token})
    })
    if not isinstance(codes, list) or len(codes) != 1:
        raise RiotError("Riot did not return a tournament code.")
    with connect() as conn:
        conn.execute("INSERT INTO riot_games (code, token, snapshot) VALUES (%s, %s, %s::jsonb)",
                     (codes[0], token, json.dumps(snapshot)))
    return codes[0]


def verified_winner(match, snapshot):
    info = match.get("info", {})
    if info.get("platformId") != "NA1" or info.get("mapId") != 11 or info.get("gameType") != "CUSTOM_GAME":
        raise RiotError("Result is not an NA Summoner's Rift custom game.")
    participants = info.get("participants", [])
    blue = {snapshot["puuids"][str(p["discord_id"])] for p in snapshot["blue"]}
    red = {snapshot["puuids"][str(p["discord_id"])] for p in snapshot["red"]}
    actual_blue = {p["puuid"] for p in participants if p.get("teamId") == 100}
    actual_red = {p["puuid"] for p in participants if p.get("teamId") == 200}
    if len(participants) != 10 or len(blue) != 5 or len(red) != 5 or blue & red:
        raise RiotError("The game must have ten distinct linked players.")
    if actual_blue != blue or actual_red != red:
        raise RiotError("Riot's team rosters differ from the bot's teams. Staff must review the result.")
    winners = [t["teamId"] for t in info.get("teams", []) if t.get("win") is True]
    if winners not in ([100], [200]):
        raise RiotError("Riot has not reported a valid winner.")
    return "blue" if winners == [100] else "red"


class TournamentService:
    def __init__(self, resolve, activity=None):
        self.resolve = resolve
        self.activity = activity
        self.runner = None
        self.task = None
        self.lock = asyncio.Lock()

    async def check(self):
        async with self.lock:
            game = pending_game()
            if not game or game["status"] != "pending":
                return
            games = await request("GET", "/lol/tournament/v5/games/by-code/" + quote(game["code"], safe=""))
            if not games:
                return
            if len(games) != 1:
                raise RiotError("Tournament code has multiple games. Staff must review it.")
            record = games[0]
            if record.get("region") != "NA1" or record.get("shortCode") != game["code"]:
                raise RiotError("Riot returned an unexpected tournament game.")
            match_id = f"NA1_{int(record['gameId'])}"
            match = await request("GET", "/lol/match/v5/matches/" + match_id)
            if match.get("metadata", {}).get("matchId") != match_id:
                raise RiotError("Riot returned a different match.")
            winner = verified_winner(match, game["snapshot"])
            await self.resolve(game, winner, match_id)

    async def callback(self, req):
        if not enabled():
            raise web.HTTPNotFound()
        game = pending_game()
        if not game:
            return web.Response(text="No pending game")
        try:
            body = await req.json()
            metadata = json.loads(body.get("metaData", "{}"))
            valid = body.get("shortCode") == game["code"] and secrets.compare_digest(
                str(metadata.get("token", "")), game["token"]
            )
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise web.HTTPForbidden()
        # The callback is a notification; only authenticated Riot API data determines the winner.
        try:
            await self.check()
        except (RiotError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            print(f"Tournament result awaiting retry: {exc}")
            raise web.HTTPServiceUnavailable()
        return web.Response(text="Received")

    async def poll(self):
        while True:
            try:
                await self.check()
            except Exception as exc:
                print(f"Tournament result check: {exc}")
            await asyncio.sleep(60)

    async def start(self):
        if self.runner is not None:
            return
        app = web.Application(client_max_size=16384)
        app.router.add_post("/riot/callback", self.callback)
        app.router.add_get("/health", self.health)
        app.router.add_get("/", self.home)
        app.router.add_get("/pcl-logo.png", self.logo)
        app.router.add_get("/riot.txt", self.verification)
        app.router.add_get("//riot.txt", self.verification)
        app.router.add_get("/api/standings", self.standings)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", int(os.getenv("PORT", "8080"))).start()
        if enabled():
            self.task = asyncio.create_task(self.poll())

    async def home(self, req):
        return web.FileResponse(Path(__file__).with_name("website") / "index.html")

    async def logo(self, req):
        return web.FileResponse(Path(__file__).with_name("website") / "pcl-logo.png")

    async def health(self, req):
        return web.json_response({"status": "ok"})

    async def verification(self, req):
        path = Path(__file__).with_name("website") / "riot.txt"
        return web.Response(text=path.read_text(encoding="utf-8").strip(), content_type="text/plain")

    async def standings(self, req):
        try:
            data = await asyncio.to_thread(public_data)
        except Exception:
            raise web.HTTPServiceUnavailable(text="Standings temporarily unavailable")
        if self.activity:
            data["activity"] = self.activity()
        return web.json_response(data, headers={"Cache-Control": "no-store"})
