import asyncio
import sys
from random import Random

import pytest
from fastapi.testclient import TestClient
from textual.errors import NoWidget
from textual.widget import Widget
from textual.widgets import Collapsible, Input, Select, Static, TabbedContent, TabPane

from wid.sessions import SavedSession
from wid.ui.app import RollerApp
from wid.ui.dialogs import Question
from wid.web.app import create_app

# The header the browser page sends with every action (see wid/web/app.py).
PAGE = {"HX-Request": "true"}


def read_saved(path) -> SavedSession:
    """The save file at ``path``, as a load reads it."""
    return SavedSession.model_validate_json(path.read_text(encoding="utf-8"))


class ScriptedRandom(Random):
    """A random source that rolls the given faces in order."""

    def __init__(self, faces):
        self.faces = iter(faces)

    def randint(self, a, b):
        return next(self.faces)


def run_app(scenario, *, size=(100, 40), rng=None, settings_path=None, recovery_path=None):
    """Start the app headless at ``size`` and run ``scenario(app, pilot)`` once it has settled."""

    async def main():
        app = RollerApp(rng=rng, settings_path=settings_path, recovery_path=recovery_path)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await scenario(app, pilot)

    asyncio.run(main())


def active_tab(app) -> str:
    return app.query_one("#details", TabbedContent).active


def collapsed(app, name: str) -> bool:
    return app.query_one(f"#{name}-section", Collapsible).collapsed


async def reveal(app, pilot, selector: str) -> Widget:
    """Make a widget visible: activate its tab, expand its sections, and scroll to it.

    Widgets inside an inactive tab or a collapsed section exist and keep their values but
    have no screen region, so tests that click, focus or measure one must call this first.
    Under load the layout can take several refreshes to settle, so this waits until the widget
    is really at its place on screen, where a click lands on it and not on what was there.
    """
    widget = app.query_one(selector)
    for ancestor in reversed(widget.ancestors):
        if isinstance(ancestor, TabPane):
            tabs = next(a for a in ancestor.ancestors if isinstance(a, TabbedContent))
            tabs.active = ancestor.id
        elif isinstance(ancestor, Collapsible):
            ancestor.collapsed = False
    for _ in range(50):
        await pilot.pause()
        widget.scroll_visible(animate=False)
        await pilot.pause()
        if lands_on(app, widget):
            return widget
    raise AssertionError(f"{selector} never settled on screen")


def lands_on(app, widget: Widget) -> bool:
    """Whether a click at the widget's corner, where the pilot clicks, would reach it."""
    try:
        under, _ = app.get_widget_at(*widget.region.offset)
    except NoWidget:
        return False
    return widget in under.ancestors_with_self


async def click(app, pilot, selector: str) -> None:
    """Reveal a widget, click it, and let the app handle the click."""
    await reveal(app, pilot, selector)
    assert await pilot.click(selector), f"the click missed {selector}"
    await pilot.pause()


def text(app, selector):
    """The text a Static widget shows."""
    return str(app.query_one(selector, Static).content)


async def start_game(app, pilot, ranks=None):
    """Set the attribute ranks, if given, and press Start game."""
    if ranks is not None:
        for index, rank in enumerate(ranks):
            app.query_one(f"#attribute-rank-{index}", Select).value = rank
    await click(app, pilot, "#start-game")
    assert app.session.attributes is not None


async def load_game(app, pilot):
    """Open Load session, check it offers the session path, and load that file."""
    await click(app, pilot, "#load-session")
    assert (
        app.screen.query_one("#load-path", Input).value
        == app.query_one("#session-path", Input).value
    )
    await pilot.click("#submit-load")
    await pilot.pause()


async def change_genre(app, pilot, genre) -> None:
    """Switch the genre kit, confirming the new game if the app asks."""
    app.query_one("#genre", Select).value = genre
    await pilot.pause()
    if isinstance(app.screen, Question):
        await pilot.click("#confirm-session")
        await pilot.pause()


def browser(game):
    """A browser signed in to the game, as if it opened the address ``wid --web`` printed."""
    client = TestClient(create_app(game, "token"), base_url="http://127.0.0.1")
    client.get("/?token=token")
    return client


def act(client, action, **fields):
    """Post an action with the sheet's fields, as the page does for every button."""
    return client.post(f"/actions/{action}", data={"sheet": "1", **fields}, headers=PAGE)


# Windows has no POSIX permission bits, umask or ``~user`` lookup; tests of those are skipped there.
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only behaviour")
