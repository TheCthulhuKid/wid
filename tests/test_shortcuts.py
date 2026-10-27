import asyncio

import pytest
from helpers import reveal, start_game
from textual.widgets import Input, Select, TabbedContent
from textual.widgets.tabbed_content import ContentTabs

from wid.profiles import Genre
from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def run(scenario, size=(100, 45)):
    async def main():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def active_tab(app):
    return app.query_one("#details", TabbedContent).active


def test_letter_shortcuts_switch_tabs_and_fold_sections():
    async def scenario(app, pilot):
        app.query_one("#fear", Select).focus()
        await pilot.press("s")
        await pilot.pause()
        assert active_tab(app) == "tab-session"
        assert isinstance(app.focused, ContentTabs)
        await pilot.press("c", "t", "i")
        await pilot.pause()
        assert active_tab(app) == "tab-character"
        assert app.query_one("#strain-section").collapsed
        assert app.query_one("#items-section").collapsed

    run(scenario)


def test_letters_are_typed_inside_a_text_field():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).focus()
        await pilot.press("c", "s", "t")
        assert app.query_one("#character-name", Input).value == "cst"
        assert not app.query_one("#strain-section").collapsed

    run(scenario)


def test_shortcuts_do_nothing_while_a_confirmation_is_open():
    async def scenario(app, pilot):
        app.session.strain = app.session.strain.take(1)
        app.query_one("#genre", Select).value = Genre.HECKBOY
        await pilot.pause()
        dialog = app.screen
        await pilot.press("s", "t")
        assert app.screen is dialog
        await pilot.click("#cancel-reset")
        await pilot.pause()
        assert active_tab(app) == "tab-character"

    run(scenario)


def test_repeat_roll_works_from_a_text_field():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        (await reveal(app, pilot, "#session-notes")).focus()
        await pilot.press("ctrl+r")
        assert len(app.history) == 1

    run(scenario)
