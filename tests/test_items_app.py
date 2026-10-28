import asyncio

import pytest
from helpers import ScriptedRandom, click, start_game, text
from textual.widgets import Button, Input, Select

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_an_item_button_waits_for_a_name_and_aims_at_the_picked_die():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([3, 2, 1, 6]))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            button = app.query_one("#apply-appropriate_item", Button)
            assert button.disabled
            app.query_one("#name-appropriate_item", Input).value = "Sword"
            await pilot.press("ctrl+r")
            await click(app, pilot, "#apply-appropriate_item")
            assert "1: 3+1=4 miss" in text(app, "#dice")
            assert button.disabled
            await click(app, pilot, "#undo")
            assert not button.disabled
            app.query_one("#item-target", Select).value = 1
            await click(app, pilot, "#apply-appropriate_item")
            assert "2: 2+1=3 miss" in text(app, "#dice")

    asyncio.run(scenario())
