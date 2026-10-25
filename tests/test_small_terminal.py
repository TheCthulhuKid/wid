import asyncio

import pytest
from helpers import reveal
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from textual.widgets import Button, Checkbox, Collapsible, Input, Select

from wid.ui.app import RollerApp

CONFIG_CONTROLS = ("#genre", "#roll-attribute-0", "#fear", "#character-name", "#assisted")
PLAY_AREA = ("#roll-attribute-2", "#fear", "#assisted", "#expertise", "#pool")


def run(scenario, size, rng=None):
    async def main():
        app = RollerApp(rng=rng)
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def collapsed(app, name):
    return app.query_one(f"#{name}-section", Collapsible).collapsed


def test_a_short_terminal_uses_one_row_controls_and_starts_collapsed():
    async def scenario(app, pilot):
        assert app.has_class("short")
        for selector in CONFIG_CONTROLS:
            assert app.query_one(selector).compact, selector
        assert collapsed(app, "strain") and collapsed(app, "items")
        assert (
            app.query_one("#strain-section", Collapsible).title
            == "Strain tracker: 0 strain, 0 wounds"
        )

    run(scenario, (80, 24))


def test_strain_boxes_keep_their_bordered_look_in_short_mode():
    async def scenario(app, pilot):
        await reveal(app, pilot, "#strain-box-0")
        assert not app.query_one("#strain-box-0", Checkbox).compact
        assert not app.query_one("#strain-box-3", Checkbox).compact

    run(scenario, (80, 24))


def test_the_whole_play_area_fits_without_scrolling_at_80x24():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        configuration = app.query_one("#configuration")
        assert configuration.scroll_offset.y == 0
        for selector in PLAY_AREA:
            region = app.query_one(selector).region
            assert region.height > 0, selector
            assert configuration.content_region.contains_region(region), selector

    run(scenario, (80, 24))


@pytest.mark.parametrize("size", [(100, 30), (100, 35), (140, 45)])
def test_a_roomy_terminal_keeps_the_full_size_controls_and_open_sections(size):
    async def scenario(app, pilot):
        assert not app.has_class("short")
        for selector in CONFIG_CONTROLS:
            assert not app.query_one(selector).compact, selector
        assert not collapsed(app, "strain") and not collapsed(app, "items")

    run(scenario, size)


@pytest.mark.parametrize(
    ("size", "short", "folded"),
    [((99, 40), False, True), ((100, 29), True, True), ((100, 30), False, False)],
)
def test_thresholds(size, short, folded):
    async def scenario(app, pilot):
        assert app.has_class("short") is short
        assert collapsed(app, "strain") is folded

    run(scenario, size)


def test_resizing_switches_short_mode_without_overriding_the_users_sections():
    async def scenario(app, pilot):
        assert not app.has_class("short")
        app.query_one("#strain-section", Collapsible).collapsed = True
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.has_class("short")
        assert app.query_one("#fear").compact
        assert not collapsed(app, "items")
        await pilot.resize_terminal(140, 45)
        await pilot.pause()
        assert not app.has_class("short")
        assert not app.query_one("#fear").compact
        assert collapsed(app, "strain")

    run(scenario, (140, 45))


def test_a_game_can_be_played_in_an_80x24_terminal():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        for selector in ("#roll-attribute-1", "#roll-attribute-0"):
            await pilot.click(selector)
            await pilot.pause()
        assert len(app.history) == 2
        assert "Athleticism (rank 1)" in text(app, "#tested-attribute")
        app.query_one("#fear", Select).value = 1
        await pilot.pause()
        assert text(app, "#pool") == "Pool: 3d6 — hits on 5+"
        app.query_one("#name-appropriate_item", Input).value = "Sword"
        await click_button(app, pilot, "#apply-appropriate_item")
        assert "Sword" in str(app.history[-1])

    async def click_button(app, pilot, selector):
        button = await reveal(app, pilot, selector)
        assert isinstance(button, Button)
        await pilot.click(button)
        await pilot.pause()

    run(scenario, (80, 24), ScriptedRandom([4] * 12))
