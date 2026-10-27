import asyncio

import pytest
from helpers import start_game, text
from textual.widgets import Button, Input

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_load_game_opens_a_prompt_with_the_session_path(tmp_path, saved_session_factory):
    path = tmp_path / "campaign.json"
    saved = saved_session_factory()
    saved.save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            assert await pilot.click("#load-session")
            await pilot.pause()
            editor = app.screen.query_one("#load-path", Input)
            assert editor.has_focus
            editor.value = str(path)
            await pilot.press("enter")
            await pilot.pause()
            assert app.session.model_dump() == saved.session.model_dump()
            assert app.query_one("#session-path", Input).value == str(path)
            assert not app.query_one("#roll-attribute-0", Button).disabled

    asyncio.run(scenario())


def test_cancelling_or_a_missing_file_keeps_the_game(tmp_path):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            before = app.session.model_dump()
            await pilot.click("#load-session")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.session.model_dump() == before
            await pilot.click("#load-session")
            await pilot.pause()
            app.screen.query_one("#load-path", Input).value = str(tmp_path / "missing.json")
            await pilot.click("#submit-load")
            await pilot.pause()
            assert "Could not load session" in text(app, "#feedback")
            assert app.session.model_dump() == before

    asyncio.run(scenario())
