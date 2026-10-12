# PCL Website

The deployed site adapts the supplied PCL concept into static HTML, CSS and
JavaScript served by the existing Python bot. No Node build is required on
Railway. The original React concept is retained in ../frontend as a reference;
it is not the deployed entry point.

- index.html: structure and copy.
- static/design.css: original concept styling.
- static/integration.css: responsive and live-data adaptations.
- static/app.js: routing, live voice and queue, standings and animation.
- previous-design.html: retained previous website.

The bot serves /, /standings, /static/*, /api/voice, /api/standings, /riot.txt
and //riot.txt. Both existing hash links and /standings work.
Queue and voice refresh every 15 seconds; standings every 30 seconds.
Sample players and rank names from the concept are not published.
Public standings stay paused according to the API's stats_hidden flag.

For a visual-only local preview:

    python -m http.server 8092 --bind 127.0.0.1 --directory website

This static preview has no bot connection and shows unavailable states.
For live data, run the actual bot with WEBSITE_ENABLED=true and DATABASE_URL,
or deploy the repository to the existing Railway bot service.

Verification:

    node --check website/static/app.js
    node tests/test_website_frontend.cjs
    python -m unittest discover -s tests
