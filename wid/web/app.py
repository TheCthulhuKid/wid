"""The FastAPI application the browser talks to: one game, reachable only from this machine.

Three checks guard every request, because save and export can write files:

- the Host header must be ``127.0.0.1`` or ``localhost``, against DNS rebinding;
- the per-launch token, which arrives once in the URL ``wid --web`` opens and is then kept in a
  ``SameSite=Strict`` cookie, so another site cannot borrow the player's session;
- actions must carry htmx's ``HX-Request`` header. Browsers only let another origin add a custom
  header after a CORS check, which this app never grants. That matters because SameSite treats
  every ``localhost`` port as the same site, so the cookie alone would not stop a page served
  by some other local program.
"""

import asyncio
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.templating import Jinja2Templates

from wid.game import Game
from wid.web.forms import ACTIONS, NeedsConfirmation, SheetForm, collect
from wid.web.view import COLOURS, css_variables, sheet_context

HOSTS = ["127.0.0.1", "localhost"]
TOKEN_COOKIE = "wid_token"
HERE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=HERE / "templates")


def matches(offered: str, token: str) -> bool:
    # Compared as bytes: compare_digest refuses non-ASCII text, which a forged cookie could hold.
    return secrets.compare_digest(offered.encode(), token.encode())


def download_name(game: Game) -> str:
    # The name goes into a response header, so only plain filename characters are kept.
    return re.sub(r"[^\w.-]", "_", Path(game.default_export_path()).name)


def render(
    request: Request,
    template: str,
    game: Game,
    message: str,
    *,
    preview: bool = False,
    ask: NeedsConfirmation | None = None,
) -> Response:
    context = sheet_context(game, message, preview=preview, ask=ask)
    context |= {"light": css_variables(COLOURS["light"]), "dark": css_variables(COLOURS["dark"])}
    return TEMPLATES.TemplateResponse(request, template, context)


def create_app(game: Game, token: str) -> FastAPI:
    # No interactive API docs: this app serves one local player, not API clients.
    app = FastAPI(title="wid", docs_url=None, redoc_url=None, openapi_url=None)
    # Requests are handled concurrently, so one action finishes before the next one starts.
    lock = asyncio.Lock()

    @app.middleware("http")
    async def require_token(request: Request, call_next) -> Response:
        offered = request.query_params.get("token")
        if offered is not None and matches(offered, token):
            # Swap the token in the address for a cookie, so it does not stay in the URL bar.
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(TOKEN_COOKIE, token, httponly=True, samesite="strict")
            return response
        if not matches(request.cookies.get(TOKEN_COOKIE, ""), token):
            return PlainTextResponse("Open wid from the address it printed when it started.", 403)
        if request.method != "GET" and request.headers.get("HX-Request") != "true":
            return PlainTextResponse("Actions only come from the wid page.", 403)
        return await call_next(request)

    # Added last so it runs first: a foreign Host never reaches the token check.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=HOSTS)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def page(request: Request) -> Response:
        async with lock:
            return render(request, "page.html", game, "")

    @app.post("/actions/{name}", response_class=HTMLResponse)
    async def act(name: str, request: Request) -> Response:
        action = ACTIONS.get(name)
        if action is None:
            raise HTTPException(404, "No such action")
        body = await request.body()
        async with lock:
            preview, ask = False, None
            try:
                form = SheetForm(body)
                preview = form.ticked("notes-preview")
                collect(game, form)
                message = action(game, form)
            except NeedsConfirmation as question:
                message, ask = "", question
            except ValueError as error:
                message = str(error)
            return render(request, "sheet.html", game, message, preview=preview, ask=ask)

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
