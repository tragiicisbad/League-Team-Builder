import unittest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from aiohttp import web
from website_auth import WebsiteAuth, digest


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_unconfigured_login_does_not_touch_database(self):
        with patch.dict("os.environ", {}, clear=True), patch("website_auth.connect") as db:
            auth = WebsiteAuth()
            with self.assertRaises(web.HTTPServiceUnavailable):
                await auth.login(None)
            db.assert_not_called()

    async def test_oauth_requires_browser_state(self):
        with patch.dict("os.environ", {"WEBSITE_PUBLIC_URL":"https://pcl.example",
                                     "DISCORD_CLIENT_ID":"123","DISCORD_CLIENT_SECRET":"test"}):
            auth = WebsiteAuth()
            with patch("website_auth.connect") as db:
                with self.assertRaises(web.HTTPForbidden):
                    await auth.callback(SimpleNamespace(query={"state":"wrong"},cookies={"__Host-pcl-oauth":"correct"}))
                db.assert_not_called()

    async def test_profile_write_rejects_cross_origin(self):
        auth = WebsiteAuth()
        auth.origin = "https://pcl.example"
        with self.assertRaises(web.HTTPForbidden):
            await auth.save(SimpleNamespace(headers={"Origin":"https://other.example"}))

    async def test_anonymous_profile_is_private(self):
        auth = WebsiteAuth()
        auth.origin = ""
        response = await auth.profile(None)
        self.assertIn('"authenticated": false', response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_session_hash_is_not_raw_token(self):
        self.assertNotEqual(digest("secret-session"), "secret-session")
        self.assertEqual(len(digest("secret-session")), 64)

    async def test_signed_up_player_overrides_old_website_preferences(self):
        import json
        auth = WebsiteAuth()
        auth.origin = "https://pcl.example"
        auth.client_id = "123"
        auth.secret = "test"
        player = {"name":"Existing", "primary_role":"ADC", "secondary_role":"Support",
                  "rank":"Gold IV", "rating":1200, "wins":5, "losses":2}
        with patch.object(auth, "current", return_value=("42", '{"name":"Discord"}', '{"name":"Old"}')), patch("website_auth.get_player", return_value=player):
            response = await auth.profile(None)
        payload = json.loads(response.text)
        self.assertTrue(payload["signup_completed"])
        self.assertEqual(payload["preferences"]["name"], "Existing")
        self.assertEqual(payload["preferences"]["primary"], "Bot")
        self.assertEqual(payload["player"]["rating"], 1200)

    async def test_synced_profile_updates_verified_discord_account(self):
        sync = AsyncMock(return_value=True)
        auth = WebsiteAuth(sync_roles=sync)
        auth.origin = "https://pcl.example"
        req = SimpleNamespace(headers={"Origin":auth.origin}, json=AsyncMock(return_value={
            "name":"Existing", "primary":"Bot", "secondary":"Support", "discord_id":"999"}))
        with patch.object(auth, "current", return_value=("42", "{}", "{}")), patch("website_auth.get_player", return_value={"name":"Existing"}), patch("website_auth.connect") as db:
            response = await auth.save(req)
            self.assertEqual(response.status, 200)
            db.assert_called_once()
        sync.assert_awaited_once_with(42, "Bot", "Support", "None")

    async def test_invalid_roles_do_not_sync(self):
        sync = AsyncMock()
        auth = WebsiteAuth(sync_roles=sync)
        auth.origin = "https://pcl.example"
        req = SimpleNamespace(headers={"Origin":auth.origin}, json=AsyncMock(return_value={
            "name":"Existing", "primary":"Top", "secondary":"Top"}))
        with patch.object(auth, "current", return_value=("42", "{}", "{}")):
            with self.assertRaises(web.HTTPBadRequest):
                await auth.save(req)
        sync.assert_not_awaited()

    async def test_queue_join_uses_authenticated_identity(self):
        join = AsyncMock(return_value="active")
        auth = WebsiteAuth(join_queue=join)
        auth.origin = "https://pcl.example"
        req = SimpleNamespace(headers={"Origin":auth.origin})
        with patch.object(auth, "current", return_value=("42", "{}", "{}")):
            response = await auth.queue_join(req)
        join.assert_awaited_once_with(42)
        self.assertEqual(response.status, 200)

    async def test_queue_join_requires_login(self):
        join = AsyncMock()
        auth = WebsiteAuth(join_queue=join)
        auth.origin = "https://pcl.example"
        req = SimpleNamespace(headers={"Origin":auth.origin})
        with patch.object(auth, "current", return_value=None):
            with self.assertRaises(web.HTTPUnauthorized):
                await auth.queue_join(req)
        join.assert_not_awaited()

    async def test_queue_leave_uses_authenticated_identity(self):
        leave = AsyncMock()
        auth = WebsiteAuth(leave_queue=leave)
        auth.origin = "https://pcl.example"
        req = SimpleNamespace(headers={"Origin":auth.origin})
        with patch.object(auth, "current", return_value=("42", "{}", "{}")):
            response = await auth.queue_leave(req)
        leave.assert_awaited_once_with(42)
        self.assertEqual(response.status, 200)

    async def test_queue_leave_rejects_cross_origin(self):
        leave = AsyncMock()
        auth = WebsiteAuth(leave_queue=leave)
        auth.origin = "https://pcl.example"
        with self.assertRaises(web.HTTPForbidden):
            await auth.queue_leave(SimpleNamespace(headers={"Origin":"https://other.example"}))
        leave.assert_not_awaited()

    async def test_ready_check_uses_verified_identity(self):
        ready = AsyncMock()
        auth = WebsiteAuth(ready_queue=ready)
        auth.origin = "https://pcl.example"
        with patch.object(auth, "current", return_value=("42", "{}", "{}")):
            response = await auth.queue_ready(SimpleNamespace(headers={"Origin":auth.origin}))
        ready.assert_awaited_once_with(42)
        self.assertEqual(response.status, 200)

    async def test_queue_status_requires_login(self):
        auth = WebsiteAuth(queue_status=lambda uid: {})
        with patch.object(auth, "current", return_value=None):
            with self.assertRaises(web.HTTPUnauthorized):
                await auth.queue_me(None)
