import asyncio

import pytest
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from textual.widgets import Button, Select

from wid.profiles import PROFILES, Genre
from wid.ui.app import RollerApp


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_attribute_buttons_roll_their_own_rank(size):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 12))
        async with app.run_test(size=size) as pilot:
            assert not app.query("#attribute")
            assert not app.query("#roll_button")
            buttons = [app.query_one(f"#roll-attribute-{index}", Button) for index in range(3)]
            assert all(button.disabled for button in buttons)
            await start_game(app, pilot, (3, 1, 2))
            for index, (button, attribute, rank) in enumerate(
                zip(buttons, PROFILES[Genre.CORE].attributes, (3, 1, 2), strict=True)
            ):
                button.scroll_visible(animate=False)
                await pilot.pause()
                row = app.query_one(f"#attribute-row-{index}")
                label = app.query_one(f"#attribute-label-{index}")
                rank_select = app.query_one(f"#attribute-rank-{index}", Select)
                assert text(app, f"#attribute-label-{index}") == attribute
                assert str(button.label) == "Roll"
                assert rank_select.display and rank_select.disabled
                assert rank_select.value == rank
                assert button.region.y == rank_select.region.y == label.region.y
                assert label.region.right <= rank_select.region.x
                assert rank_select.region.right <= button.region.x
                assert row.content_region.contains_region(button.region)
                assert app.query_one("#configuration").content_region.contains_region(button.region)
                assert await pilot.click(button)
                await pilot.pause()
                result = app.session.current_result
                assert result.request.attribute == attribute
                assert result.request.attribute_rank == rank

    asyncio.run(scenario())


def test_kit_switch_updates_all_labels_and_locks_buttons_until_setup():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 35)) as pilot:
            for genre, profile in PROFILES.items():
                app.query_one("#genre", Select).value = genre
                await pilot.pause()
                assert app.tested_attribute == profile.attributes[0]
                assert app.query_one("#attribute-setup").display
                for index, attribute in enumerate(profile.attributes):
                    assert text(app, f"#attribute-label-{index}") == attribute
                    rank = app.query_one(f"#attribute-rank-{index}", Select)
                    button = app.query_one(f"#roll-attribute-{index}", Button)
                    assert rank.display and not rank.disabled
                    assert button.disabled
                    app.action_roll_attribute(index)
                    assert app.session.current_result is None
                    assert app.tested_attribute == profile.attributes[0]
                await start_game(app, pilot)
                assert all(
                    not app.query_one(f"#roll-attribute-{index}", Button).disabled
                    for index in range(3)
                )

    asyncio.run(scenario())


@pytest.mark.parametrize("genre", list(Genre))
def test_ctrl_r_and_action_roll_repeat_last_attribute(genre):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 32))
        async with app.run_test(size=(100, 35)) as pilot:
            app.query_one("#genre", Select).value = genre
            await pilot.pause()
            await start_game(app, pilot, (2, 3, 1))
            initial_history = list(app.history)
            await pilot.press("ctrl+r")
            assert app.session.current_result.request.attribute == PROFILES[genre].attributes[0]
            assert app.session.current_result.request.attribute_rank == 2
            for index, attribute in enumerate(PROFILES[genre].attributes):
                app.action_roll_attribute(index)
                assert app.tested_attribute == attribute
                request = app.session.current_result.request
                assert request.attribute == attribute
                assert request.attribute_rank == (2, 3, 1)[index]
                await pilot.press("ctrl+r")
                assert app.session.current_result.request == request
            app.action_roll()
            assert app.session.current_result.request == request
            assert app.history[: len(initial_history)] == initial_history
            assert len(app.history) == len(initial_history) + 8

    asyncio.run(scenario())
