import asyncio

from helpers import change_genre, click
from test_rolls import ScriptedRandom
from textual.command import CommandPalette
from textual.widgets import Checkbox, Collapsible, Input, Select, Static

from wid.profiles import Genre
from wid.rolls import BonusKind
from wid.ui.app import RollerApp


def text(app, selector):
    return str(app.query_one(selector, Static).content)


async def start_game(app, pilot, ranks=None):
    if ranks is not None:
        for index, rank in enumerate(ranks):
            app.query_one(f"#attribute-rank-{index}", Select).value = rank
    await click(app, pilot, "#start-game")
    assert app.session.attributes is not None


async def apply_item(app, pilot, index=0):
    app.query_one("#name-appropriate_item", Input).value = "Tool"
    app.query_one("#item-target", Select).value = index
    await pilot.pause()
    app.apply_bonus(BonusKind.APPROPRIATE_ITEM)
    await pilot.pause()


def test_a_roll_with_options_and_an_item():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4, 6]))
        async with app.run_test(size=(120, 50)) as pilot:
            await start_game(app, pilot, (2, 1, 3))
            app.query_one("#assisted", Checkbox).value = True
            app.query_one("#expertise", Checkbox).value = True
            await pilot.pause()
            assert "5d6" in text(app, "#pool")
            await click(app, pilot, "#roll-attribute-0")
            await apply_item(app, pilot)
            assert "Athleticism (rank 2)" in text(app, "#tested-attribute")
            assert "1: 1+1=2 fumble" in text(app, "#dice")
            assert "Hits: 3" in text(app, "#summary")
            assert len(app.history) == 2
            assert not app.query_one("#assisted", Checkbox).value
            assert not app.query_one("#expertise", Checkbox).value

    asyncio.run(scenario())


def test_the_game_starts_only_with_unique_ranks():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.press("ctrl+r")
            assert "Set attributes" in text(app, "#feedback")
            app.query_one("#attribute-rank-0", Select).value = 3
            await click(app, pilot, "#start-game")
            assert text(app, "#feedback") == "Each attribute rank (1–3) can appear only once"
            assert app.session.attributes is None
            await start_game(app, pilot, (3, 1, 2))
            assert app.query_one("#attribute-rank-0", Select).disabled

    asyncio.run(scenario())


def test_tech_is_named_when_used_after_a_roll():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1] * 12))
        async with app.run_test(size=(120, 60)) as pilot:
            await change_genre(app, pilot, Genre.SECOND_CONTACT)
            await start_game(app, pilot, (1, 3, 2))
            assert app.query_one("#items-section", Collapsible).title == "Tech"
            assert not app.query_one("#item-rows").display
            await click(app, pilot, "#roll-attribute-0")
            app.query_one("#tech-name-0", Input).value = "Translator"
            app.query_one("#item-target", Select).value = 1
            await pilot.pause()
            await click(app, pilot, "#use-tech-0")
            assert "1+4=5" in text(app, "#dice")
            assert str(app.history[-1]).startswith("Tech Translator: +4 to die 2:")
            await click(app, pilot, "#sacrifice-tech-0")
            assert app.session.tech.pieces[0].strength == 0
            await click(app, pilot, "#new-scenario")
            assert app.query_one("#tech-name-0", Input).value == ""

    asyncio.run(scenario())


def test_oldheart_rerolls_selected_dice_for_corruption():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4, 6, 1]))
        async with app.run_test(size=(120, 50)) as pilot:
            assert not app.query_one("#reroll-controls").display
            await change_genre(app, pilot, Genre.OLDHEART)
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            app.query_one("#reroll-die-0", Checkbox).value = True
            await pilot.pause()
            await click(app, pilot, "#reroll_button")
            assert "1: 6+0=6 hit" in text(app, "#dice")
            assert "Corruption: +1 (session 1)" in text(app, "#resources")
            assert "Reroll dice 1" in str(app.history[-1])
            assert "1 = 1 against Corruption 1, a manifestation!" in str(app.history[-1])
            assert app.session.manifestations == ("",)

    asyncio.run(scenario())


def test_theme_picker_switches_theme():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#roll-attribute-0").focus()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, CommandPalette)
            await pilot.press(*"nord")
            await pilot.pause(0.5)
            await pilot.press("enter")
            await pilot.pause()
            assert app.theme == "nord"

    asyncio.run(scenario())
