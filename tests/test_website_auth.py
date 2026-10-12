import unittest
from types import SimpleNamespace
from unittest.mock import patch
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
