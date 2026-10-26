import asyncio

from helpers import click
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from textual.widgets import Collapsible, Input

from wid.ui.app import RollerApp


def run(scenario, size, rng=None):
    async def main():
        app = RollerApp(rng=rng)
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def collapsed(app, name):
    return app.query_one(f"#{name}-section", Collapsible).collapsed


def test_a_short_terminal_uses_one_row_controls_and_starts_folded():
    async def scenario(app, pilot):
        assert app.has_class("short")
        assert app.query_one("#fear").compact
        assert collapsed(app, "strain") and collapsed(app, "items")

    run(scenario, (80, 24))


def test_a_roomy_terminal_keeps_full_size_controls_and_open_sections():
    async def scenario(app, pilot):
        assert not app.has_class("short")
        assert not app.query_one("#fear").compact
        assert not collapsed(app, "strain") and not collapsed(app, "items")

    run(scenario, (140, 45))


def test_a_game_can_be_played_in_an_80x24_terminal():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        await click(app, pilot, "#roll-attribute-0")
        assert "Athleticism (rank 1)" in text(app, "#tested-attribute")
        app.query_one("#name-appropriate_item", Input).value = "Sword"
        await click(app, pilot, "#apply-appropriate_item")
        assert "Sword" in str(app.history[-1])

    run(scenario, (80, 24), ScriptedRandom([4] * 4))
