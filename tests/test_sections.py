import asyncio

from helpers import reveal
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from test_session_app import click_control, load_game
from textual.widgets import Collapsible, Input, Select

from wid.formatting import strain_summary
from wid.profiles import Genre
from wid.rolls import PowerMode, StrainTracker
from wid.ui.app import RollerApp


def run(scenario, rng=None, size=(100, 45)):
    async def main():
        app = RollerApp(rng=rng)
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def section(app, name):
    return app.query_one(f"#{name}-section", Collapsible)


def test_summary_text():
    assert strain_summary(StrainTracker()) == "Strain 0 / 12"
    assert strain_summary(StrainTracker().take(5)) == "Strain 5 / 12"
    assert strain_summary(StrainTracker().take(12)) == "Strain 12 / 12 — Defeat"


def test_sections_start_open_and_the_strain_title_is_a_summary():
    async def scenario(app, pilot):
        assert not section(app, "strain").collapsed
        assert not section(app, "items").collapsed
        assert section(app, "strain").title == "Strain 0 / 12"
        assert section(app, "items").title == "Items"

    run(scenario)


def test_collapsed_sections_hide_their_controls_and_keep_their_state():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        for _ in range(4):
            await click_control(app, pilot, "#take-strain")
        app.query_one("#strain-name-0", Input).value = "Ribs"
        await pilot.pause()
        before = app.session.strain
        assert before.names[0] == "Ribs"
        section(app, "strain").collapsed = True
        section(app, "items").collapsed = True
        await pilot.pause()
        assert app.query_one("#strain-box-0").region.width == 0
        assert app.query_one("#item-target").region.width == 0
        assert section(app, "strain").title == "Strain 4 / 12"
        section(app, "strain").collapsed = False
        await pilot.pause()
        assert app.query_one("#strain-box-0").region.width > 0
        assert app.session.strain == before
        assert app.query_one("#strain-name-0", Input).value == "Ribs"
        assert text(app, "#strain-total") == "Character strain: 4 / 12 marked"

    run(scenario)


def test_strain_title_follows_power_strain_while_collapsed():
    async def scenario(app, pilot):
        app.query_one("#genre", Select).value = Genre.HECKBOY
        await pilot.pause()
        await start_game(app, pilot)
        app.query_one("#power", Select).value = PowerMode.ERRATIC
        await pilot.pause()
        section(app, "strain").collapsed = True
        await pilot.pause()
        await pilot.press("ctrl+r")
        assert app.session.total_strain == 2
        assert section(app, "strain").title == "Strain 2 / 12"
        assert section(app, "strain").collapsed

    run(scenario, ScriptedRandom([4] * 7))


def test_strain_title_follows_a_load_and_a_genre_reset(tmp_path, saved_session_factory):
    path = tmp_path / "strained.json"
    saved = saved_session_factory()
    saved.session.strain = StrainTracker().take(12)
    saved.save(path)

    async def scenario(app, pilot):
        section(app, "strain").collapsed = True
        await reveal(app, pilot, "#session-path")
        app.query_one("#session-path", Input).value = str(path)
        await load_game(app, pilot)
        assert section(app, "strain").title == "Strain 12 / 12 — Defeat"
        app.query_one("#genre", Select).value = Genre.OLDHEART
        await pilot.pause()
        await pilot.click("#confirm-reset")
        await pilot.pause()
        assert section(app, "strain").title == "Strain 0 / 12"
        assert section(app, "strain").collapsed

    run(scenario)


def test_reveal_opens_a_collapsed_section_for_the_controls_inside():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        section(app, "strain").collapsed = True
        await pilot.pause()
        await click_control(app, pilot, "#take-strain")
        assert not section(app, "strain").collapsed
        assert app.session.strain.boxes[0]

    run(scenario)


def test_take_strain_button_is_above_the_strain_boxes():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        button = await reveal(app, pilot, "#take-strain")
        first_box = app.query_one("#strain-box-0")
        last_box = app.query_one("#strain-box-11")
        assert button.region.y < first_box.region.y < last_box.region.y

    run(scenario)
