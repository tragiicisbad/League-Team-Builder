# Riot automatic results and website

The bot now supports NA tournament-code games. Ordinary custom lobbies created
without the bot's tournament code are still recorded manually with `!result`.

## Hosting setup

1. Register your project at https://developer.riotgames.com and request live
   Tournament API access. Describe the Discord ready check, community teams,
   rating system, and opt-in leaderboard. Tournament-stub access cannot report
   real game results.
2. Add `RIOT_API_KEY` to your bot service's private environment settings.
   Do not post the key in Discord or commit it to Git.
3. Enable public HTTP networking on the existing bot service. The HTTP server
   listens on the hosting-provided `PORT`. Set `WEBSITE_ENABLED=true` and restart.
   The service's root URL serves the leaderboard; `/health` checks availability.
4. Set `RIOT_CALLBACK_URL` to your public address ending in `/riot/callback`.
   Riot documents restrictions on callback domains and certificates. A custom
   `.com`, `.net`, or `.org` domain is a useful choice; verify callbacks with Riot
   before live use. The bot also checks the tournament API every 60 seconds, so
   a lost callback does not lose the result.
5. Run `!riotsetup` as staff. Add the returned number as `RIOT_PROVIDER_ID` in
   your hosting settings. Do not register new providers unnecessarily: changing
   the API key or callback address requires a new provider.
6. Set `RIOT_AUTO_RESULTS=true`. Restart. Use `!riotstatus` to check configuration.
7. Temporarily set `SYNC_SLASH_COMMANDS=true` and restart to register `/linkriot`
   and `/sharehistory`, then set it back to `false`.

Existing `Procfile` still runs `python bot.py`. Both Discord and the HTTP service
run in that process. No extra Python packages are required.

## Players and games

- Players complete `/signup`, then `/linkriot riot_id:Name#NA1`.
- Linking resolves the Riot account but does not prove account ownership.
  It never grants the Discord Verified role. Riot Sign On would be a separate
  integration requiring Riot approval.
- Players choose `share_match_history:true` to appear publicly. `/sharehistory`
  changes this preference without changing the linked account. Account links
  cannot change while a tournament game is active.
- At ten players, the five-minute ready check runs. When everyone is ready,
  the bot generates teams and a tournament code if automatic results are enabled.
- In League, use the tournament-code join option. Play exactly the listed Blue
  and Red teams, with the linked accounts. Staff should check team placement.
- Riot results are fetched through the authenticated API, verified against all
  ten linked accounts and their sides, and passed into the existing ratings,
  coins, betting, and match-history flow. A reused code or unexpected roster is
  left for staff review. `!result blue` or `!result red` remains a staff fallback.
- `!clearqueue` cancels the active tournament record. Old results cannot settle
  a later game. Team swaps are blocked while a tournament code is active.
- In-progress tournament teams and betting IDs are restored after a restart.
  If recording a result was interrupted, automatic retries are blocked because
  the existing rating system uses multiple database transactions. Staff must
  review the partial changes before clearing the game.

## Website

Current season standings and manually recorded games now come directly from
`players` and `matches`, without Riot linking. Signup opts players into public
standings by default, including existing players on the first deployment of this
change. `/sharehistory false` lets a player withdraw. Historical matches are
published only if all saved names resolve to unique, currently public profiles;
renamed, missing, or duplicate names are excluded pending review.

The following original tournament-only description is superseded by this season
data behavior.

The leaderboard shows opted-in players, ratings, roles, wins, losses, and win
rates. Match history shows completed tournament games only when all ten players
currently consent. Withdrawn consent removes a player from the public leaderboard
and hides games containing that player. Pages refresh every 30 seconds.

Existing manually recorded history is not published automatically because its
stored display-name strings cannot reliably establish each participant's consent.
The website is read-only and does not expose API keys, PUUIDs, callback tokens,
or private Discord IDs.

## Verification before launch

Run `python -m unittest discover -s tests` and
`python -m py_compile bot.py database.py riot_integration.py`.
Then play one real tournament-code game with ten linked accounts. Confirm the
result, rating changes, betting settlement, restart recovery, and consent behavior
on your deployed service. Live API and deployment verification require your Riot
access and hosting configuration; local checks cannot substitute for that game.

Official reference: https://developer.riotgames.com/docs/lol#tournament-api
