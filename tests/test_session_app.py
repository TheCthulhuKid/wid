import asyncio
from random import Random

import pytest
from helpers import reveal
from test_rollerapp import start_game, text
from textual.widgets import Button, Checkbox, Input, RichLog, Select, TextArea

from wid.profiles import PROFILES, Genre
from wid.sessions import SavedSession
from wid.ui.app import RollerApp


async def click_control(app, pilot, selector):
    await reveal(app, pilot, selector)
    await pilot.click(selector)
    await pilot.pause()


async def load_game(app, pilot):
    await click_control(app, pilot, "#load-session")
    assert (
        app.screen.query_one("#load-path", Input).value
        == app.query_one("#session-path", Input).value
    )
    await pilot.click("#submit-load")
    await pilot.pause()


def test_edit_save_load_and_clear_notes(tmp_path):
    path = tmp_path / "notes.json"
    notes = "Ada 🎲\n[b]A dangerous discovery[/b]\n  Keep the map.  "

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await start_game(app, pilot)
            editor = await reveal(app, pilot, "#session-notes")
            editor.load_text(notes)
            editor.focus()
            editor.move_cursor((2, len(notes.splitlines()[-1])))
            await pilot.press("enter", "d")
            expected = notes + "\nd"
            assert editor.text == expected
            await pilot.press("tab")
            assert app.focused is not editor
            app.query_one("#genre", Select).value = Genre.BALL_SEASON
            await pilot.pause()
            assert editor.text == expected
            await start_game(app, pilot)
            app.query_one("#session-name", Input).value = "Notes campaign"
            app.query_one("#session-path", Input).value = str(path)
            await click_control(app, pilot, "#save-session")
            assert SavedSession.load(path).notes == expected

        loaded = RollerApp()
        async with loaded.run_test(size=(80, 24)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            editor = loaded.query_one("#session-notes", TextArea)
            assert editor.text == expected
            editor.load_text("")
            await click_control(loaded, pilot, "#save-session")
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert SavedSession.load(path).notes == ""

    asyncio.run(scenario())


def test_load_protects_unsaved_notes_and_legacy_save_clears_editor(tmp_path, saved_session_factory):
    path = tmp_path / "older.json"
    saved = saved_session_factory()
    path.write_text(saved.model_dump_json(exclude={"notes"}), encoding="utf-8")

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            editor = app.query_one("#session-notes", TextArea)
            editor.load_text("Unsaved notes before setup")
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            await pilot.pause()
            assert editor.text == "Unsaved notes before setup"
            assert app.session.attributes is None
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert editor.text == ""
            assert app.session.model_dump() == saved.session.model_dump()

    asyncio.run(scenario())


def test_save_and_restore_draft_independent_of_current_test(tmp_path):
    path = tmp_path / "oldheart.json"

    async def scenario():
        app = RollerApp(rng=Random(4))
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#genre", Select).value = Genre.OLDHEART
            await pilot.pause()
            await start_game(app, pilot, (3, 1, 2))
            app.query_one("#expertise", Checkbox).value = True
            await pilot.press("ctrl+r")
            app.query_one("#name-appropriate_item", Input).value = "Staff"
            await pilot.pause()
            app.apply_bonus("appropriate_item")
            app.apply_bonus("appropriate_item")
            app.query_one("#reroll-die-0", Checkbox).value = True
            await click_control(app, pilot, "#reroll_button")
            assert app.session.total_corruption == 1
            app.query_one("#fear", Select).value = 3
            app.query_one("#assisted", Checkbox).value = True
            app.tested_attribute = "Hospitality"
            app.query_one("#reroll-die-3", Checkbox).value = True
            app.query_one("#session-name", Input).value = "A dangerous evening"
            app.query_one("#session-path", Input).value = str(path)
            await pilot.pause()
            expected_session = app.session.model_dump()
            expected_draft = app.draft_request().model_dump()
            expected_history = list(app.history)
            await click_control(app, pilot, "#save-session")
            assert "Saved A dangerous evening" in text(app, "#feedback")
            assert path.exists()

        loaded = RollerApp(rng=Random(9))
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            assert loaded.session.model_dump() == expected_session
            assert loaded.draft_request().model_dump() == expected_draft
            assert loaded.query_one("#fear", Select).value == 3
            assert loaded.history == expected_history
            assert loaded.selected_dice() == {3}
            assert not loaded.query_one("#reroll_button", Button).disabled
            assert loaded.tested_attribute == "Hospitality"
            assert "Depravity (rank 3)" in text(loaded, "#tested-attribute")
            assert "2d6" in text(loaded, "#pool")
            assert "4:" in text(loaded, "#dice")
            await pilot.press("ctrl+l")
            assert loaded.query_one("#log", RichLog).lines
            assert loaded.sub_title == "A dangerous evening"
            await click_control(loaded, pilot, "#reroll_button")
            assert loaded.session.total_corruption == 2
            assert loaded.session.current_result.totals().expertise_hits == 1
            assert loaded.history[:-1] == expected_history
            await pilot.press("ctrl+r")
            assert len(loaded.session.current_result.dice) == 2
            assert loaded.session.current_result.request.attribute == "Hospitality"
            assert loaded.session.current_result.request.attribute_rank == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("genre", list(Genre))
def test_load_every_kit_and_continue_playing(tmp_path, genre, saved_session_factory):
    path = tmp_path / "session.json"
    saved = saved_session_factory(genre)
    saved.save(path)

    async def scenario():
        app = RollerApp(rng=Random(3))
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            assert app.session.model_dump() == saved.session.model_dump()
            assert app.draft_request().model_dump() == saved.draft.model_dump()
            assert app.session.current_result.dice == saved.session.current_result.dice
            assert app.query_one("#attribute-setup").display
            assert "Loaded" in text(app, "#feedback")
            await pilot.press("ctrl+r")
            assert len(app.history) == len(saved.history) + 1
            if genre == Genre.SECOND_CONTACT:
                assert app.session.tech.remaining_bonus == saved.session.tech.remaining_bonus - 1
            if genre == Genre.HECKBOY:
                assert app.session.total_strain == 2
            assert app.tested_attribute == saved.draft.attribute
            for index, attribute in enumerate(PROFILES[genre].attributes):
                assert app.query_one(f"#attribute-rank-{index}", Select).disabled
                assert not app.query_one(f"#roll-attribute-{index}", Button).disabled
                await click_control(app, pilot, f"#roll-attribute-{index}")
                assert app.session.current_result.request.attribute == attribute
                assert (
                    app.session.current_result.request.attribute_rank
                    == saved.session.attribute_rank(attribute)
                )

    asyncio.run(scenario())


def test_load_depleted_tech_without_replenishment(tmp_path, saved_session_factory):
    path = tmp_path / "depleted.json"
    saved = saved_session_factory(Genre.SECOND_CONTACT)
    for _ in range(2):
        saved.session.roll(saved.draft, rng=Random(1))
    saved = saved.model_copy(update={"draft": saved.draft.model_copy(update={"tech_target": None})})
    saved.save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            assert app.session.tech.remaining_bonus == 0
            assert app.query_one("#tech-target", Select).disabled
            assert "Tech strength: 0" in text(app, "#tech-strength")
            assert "Tech remaining: 0" in text(app, "#resources")
            app.tested_attribute = "Culture"
            await pilot.pause()
            assert app.session.tech.remaining_bonus == 0
            await pilot.press("ctrl+r")
            assert app.session.tech.remaining_bonus == 0

    asyncio.run(scenario())


def test_confirmations_errors_and_keyboard_controls(tmp_path, saved_session_factory):
    path = tmp_path / "session.json"
    saved_session_factory().save(path)
    original_file = path.read_bytes()

    async def scenario():
        app = RollerApp(rng=Random(1))
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            before = app.session.model_dump()
            history = list(app.history)
            app.query_one("#session-path", Input).value = str(path)
            app.query_one("#session-name", Input).value = "Replacement"
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            assert app.session.model_dump() == before
            assert app.history == history
            assert app.query_one("#session-name", Input).value == "Replacement"

            await click_control(app, pilot, "#save-session")
            await pilot.press("ctrl+r")
            assert app.session.model_dump() == before
            assert app.history == history
            await pilot.click("#cancel-session")
            assert path.read_bytes() == original_file
            await click_control(app, pilot, "#save-session")
            await pilot.click("#confirm-session")
            assert SavedSession.load(path).name == "Replacement"

            app.query_one("#fear", Select).value = 3
            await pilot.pause()
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            assert app.query_one("#fear", Select).value == 0
            assert app.session.model_dump() == before
            assert app.history == history

            app.query_one("#session-path", Input).value = str(tmp_path / "missing.json")
            await load_game(app, pilot)
            assert "Could not load session" in text(app, "#feedback")
            invalid_path = tmp_path / "invalid.json"
            invalid_path.write_text("invalid json", encoding="utf-8")
            app.query_one("#session-path", Input).value = str(invalid_path)
            await load_game(app, pilot)
            assert "Could not load session" in text(app, "#feedback")
            app.query_one("#session-path", Input).value = "~wid_missing_user_8a5e/session.json"
            await load_game(app, pilot)
            assert "home directory" in text(app, "#feedback")
            app.query_one("#session-path", Input).value = str(tmp_path / "missing" / "s.json")
            await click_control(app, pilot, "#save-session")
            assert "Could not save session" in text(app, "#feedback")
            assert app.session.model_dump() == before
            assert app.history == history
            assert SavedSession.load(path).session.model_dump() == before

            (await reveal(app, pilot, "#session-name")).focus()
            await pilot.press("home", "shift+end", "N", "a", "m", "e", "tab")
            assert app.query_one("#session-name", Input).value == "Name"
            assert app.focused.id == "session-notes"
            await pilot.press("tab")
            assert app.focused.id == "toggle-notes-preview"
            await pilot.press("tab", "tab", "tab", "tab")
            assert app.focused.id == "session-path"
            await pilot.press("tab")
            assert app.focused.id == "save-session"

    asyncio.run(scenario())


def test_invalid_save_keeps_game_and_file_unchanged(tmp_path):
    path = tmp_path / "not-created.json"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#session-path", Input).value = str(path)
            app.query_one("#session-name", Input).value = "Unstarted"
            await click_control(app, pilot, "#save-session")
            assert "Could not save session" in text(app, "#feedback")
            assert not path.exists()
            await start_game(app, pilot)
            for name, file_path in [
                (" ", str(path)),
                ("Name", ""),
                ("Name", "~wid_missing_user_8a5e/session.json"),
            ]:
                app.query_one("#session-name", Input).value = name
                app.query_one("#session-path", Input).value = file_path
                await click_control(app, pilot, "#save-session")
                assert "Could not save session" in text(app, "#feedback")
                assert not path.exists()
                assert app.session.current_result is None
                assert app.history == []

    asyncio.run(scenario())
