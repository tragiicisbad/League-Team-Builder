import unittest
from unittest.mock import AsyncMock, patch
from aiohttp import web

import riot_integration as riot


def fixture():
    snapshot = {
        "blue": [{"discord_id": n} for n in range(1, 6)],
        "red": [{"discord_id": n} for n in range(6, 11)],
        "puuids": {str(n): f"puuid-{n}" for n in range(1, 11)}
    }
    match = {"info": {
        "platformId": "NA1", "mapId": 11, "gameType": "CUSTOM_GAME",
        "participants": [{"puuid": f"puuid-{n}", "teamId": 100 if n <= 5 else 200}
                         for n in range(1, 11)],
        "teams": [{"teamId": 100, "win": True}, {"teamId": 200, "win": False}]
    }, "metadata": {"matchId": "NA1_123"}}
    return snapshot, match


class WinnerTests(unittest.TestCase):
    def test_blue_and_red_winners(self):
        snapshot, match = fixture()
        self.assertEqual(riot.verified_winner(match, snapshot), "blue")
        match["info"]["teams"][0]["win"] = False
        match["info"]["teams"][1]["win"] = True
        self.assertEqual(riot.verified_winner(match, snapshot), "red")

    def test_rejects_substitute(self):
        snapshot, match = fixture()
        match["info"]["participants"][0]["puuid"] = "someone-else"
        with self.assertRaises(riot.RiotError):
            riot.verified_winner(match, snapshot)

    def test_rejects_cross_team_swap(self):
        snapshot, match = fixture()
        match["info"]["participants"][0]["teamId"] = 200
        match["info"]["participants"][5]["teamId"] = 100
        with self.assertRaises(riot.RiotError):
            riot.verified_winner(match, snapshot)

    def test_rejects_wrong_region_map_or_game_type(self):
        for key, value in (("platformId", "EUW1"), ("mapId", 12), ("gameType", "MATCHED_GAME")):
            snapshot, match = fixture()
            match["info"][key] = value
            with self.subTest(key=key), self.assertRaises(riot.RiotError):
                riot.verified_winner(match, snapshot)

    def test_rejects_missing_or_multiple_winners(self):
        for value in (False, True):
            snapshot, match = fixture()
            for team in match["info"]["teams"]:
                team["win"] = value
            with self.assertRaises(riot.RiotError):
                riot.verified_winner(match, snapshot)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_cannot_supply_its_own_winner(self):
        game = {"code": "code", "token": "secret"}
        req = AsyncMock()
        req.json.return_value = {"shortCode": "code", "metaData": '{"token":"secret"}', "winner": "red"}
        service = riot.TournamentService(AsyncMock())
        service.check = AsyncMock()
        with patch.object(riot, "enabled", return_value=True), patch.object(riot, "pending_game", return_value=game):
            response = await service.callback(req)
        self.assertEqual(response.status, 200)
        service.check.assert_awaited_once_with()

    async def test_callback_rejects_invalid_secret(self):
        game = {"code": "code", "token": "secret"}
        req = AsyncMock()
        req.json.return_value = {"shortCode": "code", "metaData": '{"token":"wrong"}'}
        service = riot.TournamentService(AsyncMock())
        service.check = AsyncMock()
        with patch.object(riot, "enabled", return_value=True), patch.object(riot, "pending_game", return_value=game):
            with self.assertRaises(web.HTTPForbidden):
                await service.callback(req)
        service.check.assert_not_awaited()

    async def test_empty_history_does_not_record_result(self):
        snapshot, _ = fixture()
        game = {"code": "code", "snapshot": snapshot, "status": "pending"}
        resolve = AsyncMock()
        with patch.object(riot, "pending_game", return_value=game), patch.object(riot, "request", AsyncMock(return_value=[])):
            await riot.TournamentService(resolve).check()
        resolve.assert_not_awaited()

    async def test_interrupted_result_is_not_retried(self):
        resolve = AsyncMock()
        with patch.object(riot, "pending_game", return_value={"status": "processing"}), patch.object(riot, "request", AsyncMock()) as request:
            await riot.TournamentService(resolve).check()
        request.assert_not_awaited()
        resolve.assert_not_awaited()

    async def test_authoritative_match_is_verified_before_recording(self):
        snapshot, match = fixture()
        game = {"code": "code", "snapshot": snapshot, "status": "pending"}
        resolve = AsyncMock()
        responses = [[{"region": "NA1", "shortCode": "code", "gameId": 123}], match]
        with patch.object(riot, "pending_game", return_value=game), patch.object(riot, "request", AsyncMock(side_effect=responses)):
            await riot.TournamentService(resolve).check()
        resolve.assert_awaited_once_with(game, "blue", "NA1_123")

    async def test_multiple_games_are_not_settled(self):
        game = {"code": "code", "status": "pending"}
        resolve = AsyncMock()
        with patch.object(riot, "pending_game", return_value=game), patch.object(riot, "request", AsyncMock(return_value=[{}, {}])):
            with self.assertRaises(riot.RiotError):
                await riot.TournamentService(resolve).check()
        resolve.assert_not_awaited()

    async def test_lookup_escapes_riot_id(self):
        request = AsyncMock(return_value={"puuid": "p"})
        with patch.object(riot, "request", request):
            await riot.lookup("A Name#N/A")
        request.assert_awaited_once_with("GET", "/riot/account/v1/accounts/by-riot-id/A%20Name/N%2FA")


class PrivacyTests(unittest.TestCase):
    def test_one_nonconsenting_player_hides_whole_match(self):
        from datetime import datetime
        from unittest.mock import MagicMock
        snapshot, _ = fixture()
        for side in ("blue", "red"):
            for p in snapshot[side]:
                p.update(name="Player", assigned_role="Top")
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [[], [(n,) for n in range(1, 10)], [(snapshot, "blue", datetime.now())]]
        with patch.object(riot, "connect") as connect:
            connect.return_value.__enter__.return_value = conn
            self.assertEqual(riot.public_data()["matches"], [])

    def test_public_history_does_not_expose_private_identifiers(self):
        import json
        from datetime import datetime
        from unittest.mock import MagicMock
        snapshot, _ = fixture()
        for side in ("blue", "red"):
            for p in snapshot[side]:
                p.update(name="Player", assigned_role="Top")
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [[], [(n,) for n in range(1, 11)], [(snapshot, "blue", datetime.now())]]
        with patch.object(riot, "connect") as connect:
            connect.return_value.__enter__.return_value = conn
            result = riot.public_data()
        self.assertEqual(len(result["matches"]), 1)
        self.assertNotIn("puuid", json.dumps(result))
        self.assertNotIn("discord_id", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
