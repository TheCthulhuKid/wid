import asyncio
from random import Random

from helpers import change_genre, click
from test_rollerapp import start_game, text
from textual.widgets import Button, Checkbox, Input, Select, TextArea

from wid.profiles import Genre
from wid.sessions import SavedSession
from wid.ui.app import RollerApp


async def load_game(app, pilot):
    await click(app, pilot, "#load-session")
    assert (
        app.screen.query_one("#load-path", Input).value
        == app.query_one("#session-path", Input).value
    )
    await pilot.click("#submit-load")
    await pilot.pause()


def test_a_saved_game_loads_with_its_draft_and_history(tmp_path):
    path = tmp_path / "oldheart.json"

    async def scenario():
        app = RollerApp(rng=Random(4))
        async with app.run_test(size=(100, 40)) as pilot:
            await change_genre(app, pilot, Genre.OLDHEART)
            await start_game(app, pilot, (3, 1, 2))
            await pilot.press("ctrl+r")
            app.query_one("#fear", Select).value = 3
            app.query_one("#reroll-die-1", Checkbox).value = True
            app.query_one("#session-name", Input).value = "A dangerous evening"
            app.query_one("#session-path", Input).value = str(path)
            await pilot.pause()
            expected_session = app.session.model_dump()
            expected_history = list(app.history)
            await click(app, pilot, "#save-session")
            assert "Saved A dangerous evening" in text(app, "#feedback")

        loaded = RollerApp(rng=Random(9))
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            assert loaded.session.model_dump() == expected_session
            assert loaded.history == expected_history
            assert loaded.query_one("#fear", Select).value == 3
            assert loaded.selected_dice() == {1}
            assert loaded.sub_title == "A dangerous evening"

    asyncio.run(scenario())


def test_heckboy_power_names_are_saved_and_loaded(tmp_path):
    path = tmp_path / "heckboy.json"

    async def scenario():
        app = RollerApp(rng=Random(1))
        async with app.run_test(size=(100, 40)) as pilot:
            await change_genre(app, pilot, Genre.HECKBOY)
            await start_game(app, pilot)
            app.query_one("#power-name-0", Input).value = "Hellfire"
            app.query_one("#session-name", Input).value = "Heck"
            app.query_one("#session-path", Input).value = str(path)
            await pilot.pause()
            await click(app, pilot, "#save-session")

        loaded = RollerApp(rng=Random(2))
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            assert loaded.query_one("#power-name-0", Input).value == "Hellfire"

    asyncio.run(scenario())


def test_load_and_save_ask_before_replacing_and_report_errors(tmp_path, saved_session_factory):
    path = tmp_path / "session.json"
    saved_session_factory().save(path)
    original_file = path.read_bytes()

    async def scenario():
        app = RollerApp(rng=Random(1))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            before = app.session.model_dump()
            app.query_one("#session-path", Input).value = str(path)
            app.query_one("#session-name", Input).value = "Replacement"
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            assert app.session.model_dump() == before

            await click(app, pilot, "#save-session")
            await pilot.click("#cancel-session")
            assert path.read_bytes() == original_file
            await click(app, pilot, "#save-session")
            await pilot.click("#confirm-session")
            assert SavedSession.load(path).name == "Replacement"

            app.query_one("#session-path", Input).value = str(tmp_path / "missing.json")
            await load_game(app, pilot)
            assert "Could not load session" in text(app, "#feedback")
            app.query_one("#session-path", Input).value = str(tmp_path / "missing" / "s.json")
            await click(app, pilot, "#save-session")
            assert "Could not save session" in text(app, "#feedback")

    asyncio.run(scenario())


def test_new_character_clears_the_sheet_but_keeps_history_and_file_path():
    async def scenario():
        app = RollerApp(rng=Random(1))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            app.query_one("#character-name", Input).value = "Ada"
            app.query_one("#session-path", Input).value = "game.json"
            await pilot.press("ctrl+r")
            await click(app, pilot, "#new-character")
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert app.query_one("#character-name", Input).value == ""
            assert app.session.attributes is None
            assert app.query_one("#start-game", Button).display
            assert app.query_one("#session-path", Input).value == "game.json"
            assert str(app.history[-1]) == "New character started."

    asyncio.run(scenario())


def test_changing_genre_kit_asks_then_starts_a_new_game():
    async def scenario():
        app = RollerApp(rng=Random(1))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            app.query_one("#character-name", Input).value = "Ada"
            app.query_one("#session-notes", TextArea).load_text("Notes")
            await pilot.press("ctrl+r")
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await pilot.click("#cancel-reset")
            await pilot.pause()
            assert app.session.profile_id == Genre.CORE
            assert app.query_one("#genre", Select).value == Genre.CORE
            await change_genre(app, pilot, Genre.HECKBOY)
            assert app.session.attributes is None
            assert app.history == []
            assert app.query_one("#character-name", Input).value == ""
            assert app.query_one("#session-notes", TextArea).text == ""
            assert text(app, "#feedback") == "New Heckboy game started."

    asyncio.run(scenario())
