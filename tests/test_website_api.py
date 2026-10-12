import json
import unittest
from pathlib import Path
from aiohttp import web
import riot_integration as riot


class WebsiteAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_reads_current_queue_each_time(self):
        state = {"channels": [], "queue": {"capacity": 10, "state": "Queue open",
                                          "players": [], "waitlist": []}}
        service = riot.TournamentService(None, voice=lambda: state)
        response = await service.voice_channels(None)
        self.assertEqual(json.loads(response.text)["queue"]["players"], [])
        state["queue"]["players"].append({"name": "Test", "rank": "Gold IV"})
        response = await service.voice_channels(None)
        self.assertEqual(json.loads(response.text)["queue"]["players"][0]["rank"], "Gold IV")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    async def test_voice_unavailable_is_not_an_empty_queue(self):
        for callback in (None, lambda: None):
            with self.assertRaises(web.HTTPServiceUnavailable):
                await riot.TournamentService(None, voice=callback).voice_channels(None)

    async def test_design_assets_and_verification_are_kept(self):
        root = Path(riot.__file__).parent / "website"
        for name in ("index.html", "riot.txt", "pcl-logo.png", "static/app.js",
                     "static/design.css", "static/integration.css", "static/opening.mp4"):
            self.assertTrue((root / name).is_file(), name)
        self.assertIsInstance(await riot.TournamentService(None).home(None), web.FileResponse)
