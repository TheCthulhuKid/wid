"""The FastAPI application the browser talks to: one game, reachable only from this machine.

Three checks guard every request, because save and export can write files:

- the Host header must be ``127.0.0.1`` or ``localhost``, against DNS rebinding;
- the per-launch token, which arrives once in the URL ``wid --web`` opens and is then kept in a
  ``SameSite=Strict`` cookie, so another site cannot borrow the player's session. The cookie is
  named after the token, because browsers share cookies across ports: with one name, a second
  ``wid --web`` would replace the first one's cookie and lock its page out;
- actions must carry the ``HX-Request`` header that ``sheet.js`` adds. Browsers only let another
  origin add a custom header after a CORS check, which this app never grants. That matters
  because SameSite treats every ``localhost`` port as the same site, so the cookie alone would
  not stop a page served by some other local program.
"""

import asyncio
import hashlib
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.templating import Jinja2Templates

from wid.game import Game, player_message
from wid.web.forms import ACTIONS, NeedsConfirmation, SheetForm, collect, recovery_question
from wid.web.view import COLOURS, css_variables, sheet_context

HOSTS = ["127.0.0.1", "localhost"]
HERE = Path(__file__).parent
# The page's colours as CSS variables, worked out once (only page.html uses them).
COLOUR_VARIABLES = {scheme: css_variables(colours) for scheme, colours in COLOURS.items()}
TEMPLATES = Jinja2Templates(directory=HERE / "templates")


def token_cookie(token: str) -> str:
    """The cookie that holds this launch's token; a hash of it, so the name gives nothing away."""
    return f"wid_token_{hashlib.sha256(token.encode()).hexdigest()[:16]}"


def matches(offered: str, token: str) -> bool:
    # Compared as bytes: compare_digest refuses non-ASCII text, which a forged cookie could hold.
    return secrets.compare_digest(offered.encode(), token.encode())


def download_name(game: Game) -> str:
    # The name goes into a response header, which only carries ASCII, so anything else
    # (a quote, a line break, a letter like 日) becomes "_".
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(game.default_export_path()).name)


def render(
    request: Request,
    template: str,
    game: Game,
    message: str,
    *,
    preview: bool = False,
    ask: NeedsConfirmation | None = None,
    export_path: str = "",
) -> Response:
    context = sheet_context(game, message, preview=preview, ask=ask, export_path=export_path)
    return TEMPLATES.TemplateResponse(request, template, context | COLOUR_VARIABLES)


def create_app(game: Game, token: str, *, greeting: str = "") -> FastAPI:
    """The app for ``game``; ``greeting`` is shown once, on the first page (a file opened, say)."""
    # No interactive API docs: this app serves one local player, not API clients.
    app = FastAPI(title="wid", docs_url=None, redoc_url=None, openapi_url=None)
    # Requests are handled concurrently, so one action finishes before the next one starts.
    lock = asyncio.Lock()
    cookie = token_cookie(token)

    @app.middleware("http")
    async def require_token(request: Request, call_next) -> Response:
        offered = request.query_params.get("token")
        if offered is not None and matches(offered, token):
            # Swap the token in the address for a cookie, so it does not stay in the URL bar.
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(cookie, token, httponly=True, samesite="strict")
            return response
        if not matches(request.cookies.get(cookie, ""), token):
            return PlainTextResponse("Open wid from the address it printed when it started.", 403)
        if request.method != "GET" and request.headers.get("HX-Request") != "true":
            return PlainTextResponse("Actions only come from the wid page.", 403)
        return await call_next(request)

    # Added last so it runs first: a foreign Host never reaches the token check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=HOSTS)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def page(request: Request) -> Response:
        nonlocal greeting
        async with lock:
            message, greeting = greeting, ""
            return render(request, "page.html", game, message, ask=recovery_question(game))

    @app.post("/actions/{name}", response_class=HTMLResponse)
    async def act(name: str, request: Request) -> Response:
        action = ACTIONS.get(name)
        if action is None:
            raise HTTPException(404, "No such action")
        body = await request.body()
        async with lock:
            preview, ask, export_path = False, None, ""
            try:
                form = SheetForm(body)
                preview = form.ticked("notes-preview")
                export_path = form.text("export-path")
                collect(game, form)
                message = action(game, form)
            except NeedsConfirmation as question:
                message, ask = "", question
            except ValueError as error:
                message = player_message(error)
            if warning := game.keep_recovery():
                message = f"{message} {warning}".strip()
            return render(
                request,
                "sheet.html",
                game,
                message,
                preview=preview,
                ask=ask,
                export_path=export_path,
            )

    @app.get("/history.md")
    async def download_history() -> Response:
        async with lock:
            try:
                text = game.history_text()
            except ValueError as error:
                return PlainTextResponse(str(error), 404)
            filename = download_name(game)
        disposition = f'attachment; filename="{filename}"'
        return Response(
            text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )

    return app
