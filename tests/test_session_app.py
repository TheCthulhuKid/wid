import asyncio
from random import Random

import pytest
from helpers import change_genre, click, load_game, read_saved, start_game, text
from textual.widgets import Button, Checkbox, Input, Select, TextArea

from wid.formatting import QUIT_QUESTION
from wid.game import Game
from wid.profiles import Genre
from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_a_saved_game_loads_with_its_draft_and_history(tmp_path):
    path = tmp_path / "oldheart.json"
    details = {"name": "Ada 🎲", "looks": "Red coat", "nature": "Curious"}
    notes = "# Ada\n\n**Keep** the map.\n"

    async def scenario():
        app = RollerApp(rng=Random(4))
        async with app.run_test(size=(100, 40)) as pilot:
            await change_genre(app, pilot, Genre.OLDHEART)
            await start_game(app, pilot, (3, 1, 2))
            await pilot.press("ctrl+r")
            for field, value in details.items():
                app.query_one(f"#character-{field}", Input).value = value
            app.query_one("#session-notes", TextArea).load_text(notes)
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
            for field, value in details.items():
                assert loaded.query_one(f"#character-{field}", Input).value == value
            assert loaded.query_one("#session-notes", TextArea).text == notes

    asyncio.run(scenario())


def test_a_game_left_unsaved_is_offered_back_on_start(tmp_path):
    recovery = tmp_path / "recovery.json"
    left = Game(rng=Random(1), recovery_path=recovery)
    left.start_game((1, 2, 3))
    left.roll()
    left.keep_recovery()

    async def scenario():
        app = RollerApp(recovery_path=recovery)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert app.screen.query_one("#cancel-session", Button).label.plain == "Start fresh"
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert app.session.model_dump() == left.session.model_dump()
            assert text(app, "#feedback").startswith("Restored the game")

    asyncio.run(scenario())


def test_load_and_save_ask_before_replacing(tmp_path, saved_session_factory):
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
            assert read_saved(path).name == "Replacement"
            await pilot.press("ctrl+r")
            await pilot.press("ctrl+q")
            assert app.screen.message == QUIT_QUESTION
            await pilot.click("#cancel-session")
            assert app.is_running

    asyncio.run(scenario())


def test_new_character_and_a_new_kit_clear_the_screen():
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
            assert app.query_one("#start-game", Button).display
            assert app.query_one("#session-path", Input).value == "game.json"
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await pilot.click("#cancel-reset")
            await pilot.pause()
            assert app.query_one("#genre", Select).value == Genre.CORE
            await change_genre(app, pilot, Genre.HECKBOY)
            assert app.query_one("#session-path", Input).value == ""
            assert text(app, "#feedback") == "New Heckboy game started."

    asyncio.run(scenario())
