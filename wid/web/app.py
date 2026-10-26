"""The FastAPI application the browser talks to."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Until the sheet arrives (PLAN.md step 4), the page only confirms the server is running.
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>We're in Danger</title>
</head>
<body>
<h1>We're in Danger</h1>
<p>wid is running in your browser. The character sheet is on its way; until then, play in the
terminal with <code>wid</code>.</p>
</body>
</html>
"""


def create_app() -> FastAPI:
    # No interactive API docs: this app serves one local player, not API clients.
    app = FastAPI(title="wid", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE

    return app
