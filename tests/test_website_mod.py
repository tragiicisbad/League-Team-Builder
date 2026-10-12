import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
from website_auth import WebsiteAuth


class ModeratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_requires_authenticated_session(self):
        callback = AsyncMock()
        auth = WebsiteAuth(moderate=callback)
        auth.origin = "https://pcl.example"
        with patch.object(auth, "current", return_value=None):
            with self.assertRaises(web.HTTPUnauthorized):
                await auth.mod_write(SimpleNamespace(headers={"Origin":auth.origin}))
        callback.assert_not_awaited()

    async def test_write_uses_session_identity_not_body(self):
        callback = AsyncMock(return_value={"players":[]})
        auth = WebsiteAuth(moderate=callback)
        auth.origin = "https://pcl.example"
        body = {"action":"cancel", "discord_id":"999"}
        with patch.object(auth, "current", return_value=("42", "{}", "{}")):
            await auth.mod_write(SimpleNamespace(headers={"Origin":auth.origin},json=AsyncMock(return_value=body)))
        callback.assert_awaited_once_with(42, body)

    async def test_live_discord_role_is_required_before_database_access(self):
        tree = ast.parse(Path("bot.py").read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "website_moderate")
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=SimpleNamespace(roles=[])))
        bot = SimpleNamespace(get_guild=Mock(return_value=guild),is_ready=lambda:True)
        namespace = {"bot":bot,"website_mod_lock":asyncio.Lock()}
        exec(compile(ast.Module(body=[function],type_ignores=[]),"bot.py","exec"),namespace)
        with patch("database.get_all_player_ids") as database_read:
            with self.assertRaises(web.HTTPForbidden):
                await namespace["website_moderate"](42,{"action":"cancel"})
            database_read.assert_not_called()
        guild.fetch_member.assert_awaited_once_with(42)
