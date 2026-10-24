import asyncio

import pytest
from test_rolls import ScriptedRandom
from textual.command import CommandPalette
from textual.widgets import Button, Checkbox, Input, RichLog, Select, Static

from wid.profiles import PROFILES, Genre
from wid.rolls import BonusKind, PowerMode
from wid.ui.app import RollerApp


def text(app, selector):
    return str(app.query_one(selector, Static).content)


async def start_game(app, pilot, ranks=None):
    if ranks is not None:
        for index, rank in enumerate(ranks):
            app.query_one(f"#attribute-rank-{index}", Select).value = rank
    app.query_one("#start-game").scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click("#start-game")
    await pilot.pause()
    assert app.session.attributes is not None
    app.query_one("#genre").scroll_visible(animate=False)
    await pilot.pause()


async def apply_item(app, pilot, index=0, times=1):
    app.query_one("#name-appropriate_item", Input).value = "Tool"
    app.query_one("#item-target", Select).value = index
    await pilot.pause()
    for _ in range(times):
        app.apply_bonus(BonusKind.APPROPRIATE_ITEM)
    await pilot.pause()


@pytest.mark.parametrize("genre", list(Genre))
def test_corruption_is_only_displayed_for_oldheart(genre):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4, 6]))
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#genre", Select).value = genre
            await pilot.pause()
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            resources = text(app, "#resources")
            history = str(app.history[-1])
            if genre == Genre.OLDHEART:
                assert "Corruption: +0 (session 0)" in resources
                assert "Corruption +0 (session 0)" in history
                app.query_one("#reroll-die-0", Checkbox).value = True
                await pilot.pause()
                app.action_reroll()
                assert "Corruption: +1 (session 1)" in text(app, "#resources")
                assert "Corruption +1 (session 1)" in str(app.history[-1])
            else:
                assert "Corruption" not in resources
                assert "Corruption" not in history
            assert app.session.total_corruption == int(genre == Genre.OLDHEART)

    asyncio.run(scenario())


def test_core_flow_and_invalid_input():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4, 6]))
        async with app.run_test(size=(120, 50)) as pilot:
            await start_game(app, pilot, (2, 1, 3))
            app.query_one("#assisted", Checkbox).value = True
            app.query_one("#expertise", Checkbox).value = True
            await pilot.pause()
            assert "5d6" in text(app, "#pool")
            await pilot.click("#roll-attribute-0")
            await apply_item(app, pilot, times=2)
            assert "Athleticism (rank 2)" in text(app, "#tested-attribute")
            assert "1: 1+2=3 miss" in text(app, "#dice")
            assert "4: 4+0=4 hit" in text(app, "#dice")
            assert "Hits: 3" in text(app, "#summary")
            assert len(app.history) == 3
            assert "rank 2" in str(app.history[0])
            await pilot.press("ctrl+l")
            assert app.query_one("#log", RichLog).lines
            previous = app.session.current_result
            app.query_one("#name-appropriate_item", Input).value = " "
            await pilot.pause()
            app.apply_bonus(BonusKind.APPROPRIATE_ITEM)
            assert app.session.current_result is previous
            assert len(app.history) == 3
            assert "name" in text(app, "#feedback").lower()
            app.query_one("#name-appropriate_item", Input).focus()
            await pilot.press("home", "shift+end", "A", "x", "e", "tab")
            assert app.query_one("#name-appropriate_item", Input).value == "Axe"

    asyncio.run(scenario())


@pytest.mark.parametrize("genre", list(Genre))
def test_three_attribute_buttons_support_keyboard_rolls(genre):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4] * 3))
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#genre", Select).value = genre
            await pilot.pause()
            for index in range(3):
                assert app.query_one(f"#attribute-rank-{index}", Select).display
            await start_game(app, pilot, (3, 1, 2))
            for index, rank in enumerate((3, 1, 2)):
                button = app.query_one(f"#roll-attribute-{index}", Button)
                button.scroll_visible(animate=False)
                await pilot.pause()
                button.focus()
                await pilot.press("enter")
                assert app.tested_attribute == PROFILES[genre].attributes[index]
                assert app.session.current_result.request.attribute == app.tested_attribute
                assert app.session.current_result.request.attribute_rank == rank
                assert f"(rank {rank})" in text(app, "#tested-attribute")
                assert app.session.current_result.totals().fumbles == rank

    asyncio.run(scenario())


@pytest.mark.parametrize("genre", list(Genre))
def test_attribute_mouse_buttons_roll_each_attribute(genre):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4] * 3))
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#genre", Select).value = genre
            await pilot.pause()
            await start_game(app, pilot, (3, 1, 2))
            for index, attribute in enumerate(PROFILES[genre].attributes):
                button = app.query_one(f"#roll-attribute-{index}", Button)
                button.scroll_visible(animate=False)
                await pilot.pause()
                assert await pilot.click(button)
                await pilot.pause()
                assert app.tested_attribute == attribute
                result = app.session.current_result
                assert result.request.attribute == attribute
                assert result.request.attribute_rank == (3, 1, 2)[index]

    asyncio.run(scenario())


def test_minimum_roll_accepts_an_item():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4]))
        async with app.run_test(size=(80, 24)) as pilot:
            await start_game(app, pilot)
            app.query_one("#fear", Select).value = 3
            await pilot.pause()
            assert "1d6" in text(app, "#pool")
            await pilot.press("ctrl+r")
            await apply_item(app, pilot)
            assert len(app.session.current_result.dice) == 1
            assert "1: 4+1=5 hit" in text(app, "#dice")

    asyncio.run(scenario())


def test_genres_power_maximum_and_reset_confirmation():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([6] * 7))
        async with app.run_test(size=(120, 50)) as pilot:
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await start_game(app, pilot)
            assert app.query_one("#powers").display
            assert app.tested_attribute == "Aberrance"
            app.query_one("#assisted", Checkbox).value = True
            app.query_one("#power", Select).value = PowerMode.ERRATIC
            await pilot.pause()
            assert "7d6" in text(app, "#pool")
            await pilot.click("#roll-attribute-0")
            await apply_item(app, pilot, index=6, times=2)
            assert "7: 6+2=8 hit" in text(app, "#dice")
            assert "Strain: +2 (session 2)" in text(app, "#resources")
            app.show_result(app.session.current_result)
            assert app.session.total_strain == 2
            app.query_one("#power", Select).value = PowerMode.NONE
            await pilot.pause()
            assert app.query_one("#item-target", Select).value == 6
            assert app.session.current_result.dice[6].bonus == 2
            app.query_one("#genre", Select).value = Genre.BALL_SEASON
            await pilot.pause()
            await pilot.click("#cancel-reset")
            assert app.session.profile_id == Genre.HECKBOY
            assert app.query_one("#genre", Select).value == Genre.HECKBOY
            assert app.session.total_strain == 2
            app.query_one("#genre", Select).value = Genre.BALL_SEASON
            await pilot.pause()
            await pilot.click("#confirm-reset")
            assert app.session.profile_id == Genre.BALL_SEASON
            assert app.session.attributes is None
            assert app.session.current_result is None
            assert app.session.total_strain == 0
            assert not app.query_one("#powers").display
            await start_game(app, pilot)
            for genre, profile in PROFILES.items():
                app.query_one("#genre", Select).value = genre
                await pilot.pause()
                await start_game(app, pilot)
                for index, attribute in enumerate(profile.attributes):
                    assert text(app, f"#attribute-label-{index}") == attribute
                assert app.query_one("#items").display == profile.uses_items

    asyncio.run(scenario())


def test_tech_widgets_depletion_draft_edits_and_reset():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1] * 12))
        async with app.run_test(size=(120, 60)) as pilot:
            app.query_one("#genre", Select).value = Genre.SECOND_CONTACT
            await pilot.pause()
            await start_game(app, pilot, (2, 1, 3))
            assert app.query_one("#items").display
            assert app.query_one("#tech-controls").display
            assert app.query_one("#tech-target", Select).disabled
            button = app.query_one("#initialize-tech")
            button.scroll_visible()
            await pilot.pause()
            await pilot.click("#initialize-tech")
            assert app.session.tech.remaining_bonus == 3
            assert "Science 2 + Culture 1" in text(app, "#tech-attributes")
            assert not app.query_one("#tech-target", Select).disabled
            app.query_one("#tech-target", Select).value = 0
            app.query_one("#roll-attribute-0").scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click("#roll-attribute-0")
            assert app.session.tech.remaining_bonus == 2
            assert "1+3=4" in text(app, "#dice")
            snapshot = str(app.history[-1])
            app.tested_attribute = "Culture"
            await pilot.pause()
            assert app.tested_attribute == "Culture"
            assert app.session.tech.remaining_bonus == 2
            await pilot.click("#roll-attribute-1")
            assert app.session.tech.remaining_bonus == 1
            assert app.session.current_result.request.attribute_rank == 1
            await pilot.pause(0.4)
            await pilot.click("#roll-attribute-1")
            assert app.session.tech.remaining_bonus == 0
            assert "1+1=2" in text(app, "#dice")
            assert app.query_one("#tech-target", Select).disabled
            assert app.query_one("#tech-target", Select).value == -1
            assert "Tech strength: 0" in text(app, "#tech-strength")
            assert "depleted" in text(app, "#feedback")
            assert snapshot in [str(entry) for entry in app.history]
            assert "Tech remaining 2" in snapshot
            app.query_one("#initialize-tech").scroll_visible()
            await pilot.pause()
            await pilot.click("#initialize-tech")
            assert app.session.tech.remaining_bonus == 3
            app.query_one("#tech-target", Select).value = 3
            app.query_one("#fear", Select).value = 3
            await pilot.pause()
            assert app.query_one("#tech-target", Select).value == -1
            assert "out-of-range Tech target" in text(app, "#feedback")
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#cancel-reset")
            assert app.session.tech.remaining_bonus == 3
            assert app.session.attributes.ranks == (2, 1, 3)
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#confirm-reset")
            assert app.session.tech is None
            assert not app.query_one("#tech-controls").display

    asyncio.run(scenario())


def test_oldheart_rerolls_preserve_test_and_history():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4, 6, 1, 2]))
        async with app.run_test(size=(120, 50)) as pilot:
            assert not app.query_one("#reroll-controls").display
            app.query_one("#genre", Select).value = Genre.OLDHEART
            await pilot.pause()
            await start_game(app, pilot)
            assert app.query_one("#reroll-controls").display
            assert app.query_one("#reroll_button", Button).disabled
            app.query_one("#expertise", Checkbox).value = True
            await pilot.click("#roll-attribute-0")
            await apply_item(app, pilot, times=2)
            original = app.session.current_result
            snapshot = str(app.history[-1])
            app.query_one("#reroll-die-0", Checkbox).value = True
            app.query_one("#reroll-die-2", Checkbox).value = True
            await pilot.pause()
            assert not app.query_one("#reroll_button", Button).disabled
            app.tested_attribute = "Fitness"
            app.query_one("#fear", Select).value = 3
            app.query_one("#assisted", Checkbox).value = True
            app.query_one("#expertise", Checkbox).value = False
            app.query_one("#name-appropriate_item", Input).value = "Different draft name"
            await pilot.pause()
            await pilot.click("#reroll_button")
            assert app.session.total_corruption == 2
            assert app.session.current_result.request == original.request
            assert "1: 6+2=8 hit" in text(app, "#dice")
            assert "Hits: 2 (dice 1, expertise 1)" in text(app, "#summary")
            assert "Corruption: +2 (session 2)" in text(app, "#resources")
            assert "Reroll dice 1, 3" in str(app.history[-1])
            assert str(app.history[-2]) == snapshot
            assert "raw 1 +2 = 3" in snapshot
            assert app.query_one("#reroll_button", Button).disabled
            app.query_one("#reroll-die-0", Checkbox).value = True
            await pilot.pause(0.4)
            await pilot.click("#reroll_button")
            assert app.session.total_corruption == 3
            assert "1: 2+2=4 miss" in text(app, "#dice")
            assert app.session.current_result.totals().expertise_hits == 1
            previous = app.session.current_result
            app.action_reroll()
            assert app.session.current_result is previous
            assert app.session.total_corruption == 3
            assert "Select at least one" in text(app, "#feedback")
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#confirm-reset")
            assert app.session.total_corruption == 0
            assert app.session.current_result is None
            assert not app.query_one("#reroll-controls").display

    asyncio.run(scenario())


def test_maximum_pool_scrolls_in_compact_terminal():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 7))
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await start_game(app, pilot)
            app.query_one("#assisted", Checkbox).value = True
            app.query_one("#power", Select).value = PowerMode.ERRATIC
            await pilot.pause()
            await pilot.press("ctrl+r")
            assert len(app.session.current_result.dice) == 7
            assert "7: 4+0=4 hit" in text(app, "#dice")
            summary = app.query_one("#summary", Static)
            summary.scroll_visible(animate=False)
            await pilot.pause()
            assert summary.region.overlaps(app.query_one("RollerGroup").content_region)
            assert "Hits: 7" in text(app, "#summary")

    asyncio.run(scenario())


def test_theme_picker_opens_and_switches_theme():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            previous_theme = app.theme
            app.query_one("#roll-attribute-0").focus()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, CommandPalette)
            await pilot.press(*"nord")
            await pilot.pause(0.5)
            await pilot.press("enter")
            await pilot.pause()
            assert app.theme == "nord" != previous_theme
            assert not isinstance(app.screen, CommandPalette)

    asyncio.run(scenario())


def test_startup_and_genre_setup_require_unique_fixed_attributes():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4] * 3))
        async with app.run_test(size=(120, 50)) as pilot:
            assert app.query_one("#attribute-setup").display
            assert all(app.query_one(f"#roll-attribute-{i}", Button).disabled for i in range(3))
            await pilot.press("ctrl+r")
            assert app.session.current_result is None
            assert not app.history
            assert "Set attributes" in text(app, "#feedback")
            await start_game(app, pilot, (3, 1, 2))
            assert app.query_one("#attribute-setup").display
            assert app.session.attribute_rank("Athleticism") == 3

            app.query_one("#genre", Select).value = Genre.BALL_SEASON
            await pilot.pause()
            assert app.query_one("#attribute-setup").display
            assert all(app.query_one(f"#roll-attribute-{i}", Button).disabled for i in range(3))
            assert app.session.attributes is None
            app.query_one("#attribute-rank-0", Select).value = 3
            app.query_one("#start-game").scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click("#start-game")
            assert "only once" in text(app, "#feedback")
            assert app.session.attributes is None
            assert app.query_one("#attribute-rank-0", Select).value == 3
            assert app.query_one("#attribute-rank-2", Select).value == 3
            await pilot.press("ctrl+r")
            assert app.session.current_result is None

            app.query_one("#attribute-rank-1", Select).value = 1
            app.query_one("#attribute-rank-2", Select).value = 2
            await pilot.pause(0.4)
            app.query_one("#start-game").focus()
            await pilot.press("enter")
            assert app.session.attributes.ranks == (3, 1, 2)
            assert app.query_one("#attribute-setup").display
            assert all(app.query_one(f"#attribute-rank-{i}", Select).disabled for i in range(3))
            app.query_one("#attribute-rank-0", Select).value = 1
            assert app.session.attributes.ranks == (3, 1, 2)
            for index, (attribute, rank) in enumerate(
                zip(PROFILES[Genre.BALL_SEASON].attributes, (3, 1, 2), strict=True)
            ):
                await pilot.pause()
                app.action_roll_attribute(index)
                assert f"{attribute} (rank {rank})" in text(app, "#tested-attribute")
                assert app.session.current_result.request.attribute == attribute
                assert app.session.current_result.request.attribute_rank == rank
                assert app.session.current_result.totals().fumbles == rank

    asyncio.run(scenario())
