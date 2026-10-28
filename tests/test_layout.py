import asyncio

import pytest
from helpers import ScriptedRandom, reveal, start_game, text
from textual.widgets import Button, Collapsible, RichLog, Select

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def collapsed(app, name):
    return app.query_one(f"#{name}-section", Collapsible).collapsed


@pytest.mark.parametrize("size", [(80, 24), (140, 45)])
def test_controls_line_up_and_fit_the_panel(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            # A short terminal uses one-row controls and starts with its sections folded.
            short = size == (80, 24)
            assert (app.has_class("short"), app.query_one("#fear").compact) == (short, short)
            assert (collapsed(app, "strain"), collapsed(app, "items")) == (short, short)
            configuration = app.query_one("#configuration")
            output = app.query_one("#output")
            assert abs(configuration.region.width - 2 * output.region.width) <= 2
            genre = app.query_one("#genre", Select)
            assert app.query_one("#start-game", Button).region.y == genre.region.y
            label = app.query_one("#attribute-label-0")
            rank = app.query_one("#attribute-rank-0")
            roll = app.query_one("#roll-attribute-0")
            assert label.region.y == rank.region.y == roll.region.y
            await start_game(app, pilot)
            fear = app.query_one("#fear", Select)
            assert fear.region.y == app.query_one("#assisted").region.y
            field = await reveal(app, pilot, "#strain-name-0")
            assert configuration.content_region.contains_region(field.region)

    asyncio.run(scenario())


def test_history_toggle_shows_the_log():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4]))
        async with app.run_test(size=(80, 24)) as pilot:
            panel = app.query_one("#history-panel")
            assert not panel.display
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert panel.display
            assert str(app.query_one("#toggle-history", Button).label) == "Hide log"
            assert app.query_one("#log", RichLog).lines
            assert "1:" in text(app, "#dice")

    asyncio.run(scenario())


def test_layout_adapts_on_resize_without_losing_edits():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(140, 45)) as pilot:
            field = await reveal(app, pilot, "#strain-name-0")
            field.value = "Broken ribs"
            await pilot.pause()
            await pilot.resize_terminal(80, 24)
            await pilot.pause()
            await pilot.resize_terminal(140, 45)
            await pilot.pause()
            assert field.value == "Broken ribs"
            assert app.session.strain.names[0] == "Broken ribs"

    asyncio.run(scenario())
