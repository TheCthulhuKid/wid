import asyncio

import pytest
from helpers import ScriptedRandom, change_genre, click, start_game, text
from textual.widgets import Button

from wid.profiles import PROFILES, Genre
from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_each_attribute_button_rolls_its_rank_and_ctrl_r_repeats_it():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 16))
        async with app.run_test(size=(100, 35)) as pilot:
            assert app.query_one("#roll-attribute-0", Button).disabled
            await start_game(app, pilot, (3, 1, 2))
            for index, (attribute, rank) in enumerate(
                zip(PROFILES[Genre.CORE].attributes, (3, 1, 2), strict=True)
            ):
                await click(app, pilot, f"#roll-attribute-{index}")
                request = app.session.current_result.request
                assert (request.attribute, request.attribute_rank) == (attribute, rank)
            await pilot.press("ctrl+r")
            assert app.session.current_result.request.attribute == "Reasoning"

    asyncio.run(scenario())


def test_changing_kit_relabels_the_attributes():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 35)) as pilot:
            await change_genre(app, pilot, Genre.OLDHEART)
            labels = [text(app, f"#attribute-label-{index}") for index in range(3)]
            assert labels == list(PROFILES[Genre.OLDHEART].attributes)
            assert app.game.tested_attribute == "Depravity"

    asyncio.run(scenario())
