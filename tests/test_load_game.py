import asyncio

import pytest
from textual.widgets import Input

from wid.ui.app import RollerApp
from wid.ui.dialogs import LoadGame

pytestmark = pytest.mark.ui


def test_the_load_prompt_takes_the_focus_loads_on_enter_and_cancels_on_escape(
    tmp_path, saved_session_factory
):
    path = tmp_path / "campaign.json"
    saved = saved_session_factory()
    saved.save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.click("#load-session")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, LoadGame)
            await pilot.click("#load-session")
            await pilot.pause()
            editor = app.screen.query_one("#load-path", Input)
            assert editor.has_focus
            editor.value = str(path)
            await pilot.press("enter")
            await pilot.pause()
            assert app.session.model_dump() == saved.session.model_dump()

    asyncio.run(scenario())
