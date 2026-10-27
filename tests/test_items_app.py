import asyncio

import pytest
from helpers import ScriptedRandom, click, start_game, text
from textual.widgets import Button, Input, Select

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_named_items_and_expertise_apply_after_a_roll_and_can_be_undone():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([3, 2, 1, 6]))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            assert app.query_one("#apply-appropriate_item", Button).disabled
            app.query_one("#name-appropriate_item", Input).value = "Sword"
            app.query_one("#name-expertise", Input).value = "Fencing"
            await pilot.press("ctrl+r")
            await click(app, pilot, "#apply-appropriate_item")
            assert "1: 3+1=4 miss" in text(app, "#dice")
            assert app.query_one("#apply-appropriate_item", Button).disabled
            assert "Sword" in str(app.history[-1])
            await click(app, pilot, "#apply-expertise")
            assert app.session.current_result.totals().expertise_hits == 1
            await click(app, pilot, "#undo")
            await click(app, pilot, "#undo")
            assert "1: 3+0=3 miss" in text(app, "#dice")
            assert str(app.history[-1]).startswith("Undid the last bonus.")
            app.query_one("#item-target", Select).value = 1
            await click(app, pilot, "#apply-appropriate_item")
            assert "2: 2+1=3 miss" in text(app, "#dice")

    asyncio.run(scenario())
