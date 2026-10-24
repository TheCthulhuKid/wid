import asyncio

import pytest
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from test_session_app import load_game
from textual.widgets import Button, Checkbox, Input, Select

from wid.profiles import Genre
from wid.sessions import SavedSession
from wid.ui.app import RollerApp


async def click_visible(app, pilot, selector):
    await pilot.pause()
    control = app.query_one(selector)
    control.scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(control)
    await pilot.pause()


@pytest.mark.parametrize("genre", list(Genre))
def test_named_items_apply_repeatedly_after_roll_in_every_kit(genre):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([3, 2, 1, 6, 1]))
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#genre", Select).value = genre
            await pilot.pause()
            await start_game(app, pilot)
            assert app.query_one("#apply-appropriate_item", Button).disabled
            app.query_one("#name-appropriate_item", Input).value = "Sword [bold]"
            app.query_one("#name-inappropriate_item", Input).value = "Teacup"
            app.query_one("#name-expertise", Input).value = "Fencing"
            await pilot.press("ctrl+r")
            original = app.session.current_result
            history = list(app.history)
            for _ in range(2):
                await click_visible(app, pilot, "#apply-appropriate_item")
            assert "1: 3+2=5 hit" in text(app, "#dice")
            app.query_one("#item-target", Select).value = 1
            await click_visible(app, pilot, "#apply-inappropriate_item")
            assert "2: 2+1=3 miss" in text(app, "#dice")
            await click_visible(app, pilot, "#apply-expertise")
            assert app.session.current_result.totals().expertise_hits == 1
            assert app.query_one("#apply-expertise", Button).disabled
            assert original.dice[0].bonus == 0
            assert app.history[:-4] == history
            assert len(app.history) == len(history) + 4
            assert "Sword [bold]" in str(app.history[-4])
            assert "Teacup" in str(app.history[-2])
            assert "Fencing" in str(app.history[-1])
            assert app.session.total_strain == app.session.total_corruption == 0
            app.query_one("#fear", Select).value = 3
            await pilot.pause()
            assert app.query_one("#item-target", Select).value == 1
            await pilot.press("ctrl+r")
            assert len(app.session.current_result.dice) == 1
            assert app.query_one("#item-target", Select).value == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (140, 45)])
def test_aligned_options_and_red_wound_highlights(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await start_game(app, pilot)
            assert not app.query("#rank")
            controls = [
                app.query_one(selector) for selector in ("#fear", "#assisted", "#expertise")
            ]
            assert len({control.region.y for control in controls}) == 1
            app.session.strain = app.session.strain.take(12)
            app.update_strain_controls()
            await pilot.pause()
            strain = app.query_one("#strain-box-0", Checkbox)
            for index in (3, 7, 11):
                wound = app.query_one(f"#strain-box-{index}", Checkbox)
                assert wound.styles.background != strain.styles.background
                assert wound.styles.background.r > wound.styles.background.g
                assert wound.get_component_styles("toggle--button").background.r > (
                    wound.get_component_styles("toggle--button").background.g
                )
            for index in (11, 7, 3):
                await click_visible(app, pilot, f"#strain-box-{index}")
                assert not app.session.strain.boxes[index]

    asyncio.run(scenario())


def test_names_target_and_post_roll_bonuses_survive_save_load(tmp_path):
    path = tmp_path / "named.json"

    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 4))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            for kind, name in (
                ("expertise", "Healing"),
                ("appropriate_item", "Kit"),
                ("inappropriate_item", "Book"),
            ):
                app.query_one(f"#name-{kind}", Input).value = name
            await pilot.press("ctrl+r")
            app.query_one("#item-target", Select).value = 3
            await click_visible(app, pilot, "#apply-appropriate_item")
            await click_visible(app, pilot, "#apply-expertise")
            app.query_one("#session-name", Input).value = "Names"
            app.query_one("#session-path", Input).value = str(path)
            await click_visible(app, pilot, "#save-session")
            expected = SavedSession.load(path)
        loaded = RollerApp()
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            assert loaded.session.model_dump() == expected.session.model_dump()
            assert loaded.query_one("#name-expertise", Input).value == "Healing"
            assert loaded.query_one("#name-appropriate_item", Input).value == "Kit"
            assert loaded.query_one("#name-inappropriate_item", Input).value == "Book"
            assert loaded.query_one("#item-target", Select).value == 3
            await click_visible(loaded, pilot, "#apply-inappropriate_item")
            assert loaded.session.current_result.dice[3].bonus == 2
            assert loaded.session.current_result.totals().expertise_hits == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("genre", [Genre.HECKBOY, Genre.SECOND_CONTACT, Genre.OLDHEART])
def test_bonus_history_does_not_report_another_resource_cost(
    genre, saved_session_factory, tmp_path
):
    saved = saved_session_factory(genre)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.finish_load(saved, tmp_path / "existing.json", True)
            before = app.session.model_dump(exclude={"current_result", "bonuses"})
            app.query_one("#name-appropriate_item", Input).value = "Tool"
            await click_visible(app, pilot, "#apply-appropriate_item")
            assert "Strain +0" in str(app.history[-1])
            if genre == Genre.OLDHEART:
                assert "Corruption +0" in str(app.history[-1])
            else:
                assert "Corruption" not in str(app.history[-1])
                assert "Corruption" not in text(app, "#resources")
            assert app.session.model_dump(exclude={"current_result", "bonuses"}) == before

    asyncio.run(scenario())
