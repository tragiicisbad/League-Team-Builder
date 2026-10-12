# Discord website sign-in

In the Discord Developer Portal, select the existing PCL bot application.
Under OAuth2, add this exact redirect:

https://league-team-builder-production.up.railway.app/auth/discord/callback

Set these Railway variables on the bot service:

- DISCORD_CLIENT_ID: application/client ID from the application.
- DISCORD_CLIENT_SECRET: OAuth2 client secret, not the bot token.
- WEBSITE_PUBLIC_URL: https://league-team-builder-production.up.railway.app

Never paste the client secret into chat, source files or the website.
Redeploy after setting the variables.

Only the identify scope is requested. No email, Discord password or access
to messages is requested. Discord OAuth tokens are not saved. Random session
tokens are stored only as hashes in PostgreSQL; cookies are Secure, HttpOnly
and SameSite=Lax. OAuth states expire after ten minutes and are single-use.
Website sessions expire after seven days and logout revokes the current session.

Existing /signup players share their primary and secondary roles with the website.
Website saves update the bot signup, rating, queue entry and primary Discord role.
Discord changes appear when the website profile is opened again. Player names,
avoided roles, lane ratings and match history are preserved.
Players without /signup can save private website preferences only.
Sign-in does not automatically join the Discord server, grant Verified, complete
/signup or link a Riot account. Riot linking remains a future step.
Existing browser-only drafts are not automatically imported.

Local static previews cannot perform sign-in. Use the HTTPS Railway service.
