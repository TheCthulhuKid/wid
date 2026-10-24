import asyncio

import pytest
from helpers import reveal
from test_rollerapp import start_game
from test_session_app import click_control, load_game
from textual.widgets import Input, Select

from wid.profiles import Genre
from wid.sessions import CharacterDetails, SavedSession
from wid.ui.app import RollerApp


@pytest.mark.parametrize("genre", list(Genre))
def test_character_details_round_trip(tmp_path, saved_session_factory, genre):
    details = CharacterDetails(name="Ada 🎲", looks="  Red coat  ", nature="[bold]Curious[/bold]")
    data = saved_session_factory(genre).model_dump()
    data["character"] = details.model_dump()
    saved = SavedSession.model_validate(data)
    path = tmp_path / "character.json"
    saved.save(path)
    assert SavedSession.load(path).character == details
    del data["character"]
    assert SavedSession.model_validate(data).character == CharacterDetails()


@pytest.mark.parametrize("field", ["name", "looks", "nature"])
def test_character_details_reject_non_text(field):
    with pytest.raises(ValueError):
        CharacterDetails.model_validate({field: 42})


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_character_fields_layout_and_editing(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await reveal(app, pilot, "#character-name")
            fields = [
                app.query_one(f"#character-{field}", Input) for field in ("name", "looks", "nature")
            ]
            assert fields[0].region.y >= app.query_one("#genre").region.bottom
            assert len({field.region.y for field in fields}) == 1
            for field in fields:
                assert app.query_one("#configuration").content_region.contains_region(field.region)
                assert await pilot.click(field)
                await pilot.press("A", "d", "a")
                assert field.value == "Ada"

    asyncio.run(scenario())


def test_character_edit_save_load_and_clear(tmp_path):
    path = tmp_path / "character.json"
    details = {"name": "Ada 🎲", "looks": "Red coat", "nature": "Curious"}

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for field, value in details.items():
                app.query_one(f"#character-{field}", Input).value = value
            app.query_one("#genre", Select).value = Genre.BALL_SEASON
            await pilot.pause()
            await start_game(app, pilot)
            app.query_one("#session-name", Input).value = "Campaign"
            app.query_one("#session-path", Input).value = str(path)
            await click_control(app, pilot, "#save-session")
            assert SavedSession.load(path).character.model_dump() == details

        loaded = RollerApp()
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            for field, value in details.items():
                editor = loaded.query_one(f"#character-{field}", Input)
                assert editor.value == value
                editor.value = ""
            await click_control(loaded, pilot, "#save-session")
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert SavedSession.load(path).character == CharacterDetails()

    asyncio.run(scenario())


@pytest.mark.parametrize("field", ["name", "looks", "nature"])
def test_load_protects_character_details_and_legacy_save_clears_them(
    tmp_path, saved_session_factory, field
):
    path = tmp_path / "legacy.json"
    saved = saved_session_factory()
    path.write_text(saved.model_dump_json(exclude={"character"}), encoding="utf-8")

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            editor = app.query_one(f"#character-{field}", Input)
            editor.value = "Unsaved character"
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            await pilot.pause()
            assert editor.value == "Unsaved character"
            assert app.session.attributes is None
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert editor.value == ""
            assert app.session.model_dump() == saved.session.model_dump()

    asyncio.run(scenario())
