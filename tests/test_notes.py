import asyncio

from helpers import click
from test_rollerapp import start_game
from test_session_app import load_game
from textual.document._document import Selection
from textual.widgets import Input, Markdown, TextArea

from wid.sessions import SavedSession
from wid.ui.app import RollerApp


def test_preview_renders_markdown_and_keeps_the_source():
    notes = "# Campaign 🎲\n\n**Danger** and *hope*\n\n- Keep the map"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 35)) as pilot:
            editor = app.query_one("#session-notes", TextArea)
            preview = app.query_one("#notes-preview", Markdown)
            editor.load_text(notes)
            await click(app, pilot, "#toggle-notes-preview")
            assert not editor.display
            assert preview.source == notes
            assert preview.query("MarkdownH1")
            await click(app, pilot, "#toggle-notes-preview")
            assert editor.display
            assert editor.text == notes

    asyncio.run(scenario())


def test_formatting_buttons_wrap_the_selection_and_can_be_undone():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            editor = app.query_one("#session-notes", TextArea)
            editor.load_text("A clue")
            editor.selection = Selection((0, 2), (0, 6))
            await click(app, pilot, "#notes-bold")
            assert editor.text == "A **clue**"
            await pilot.press("ctrl+z")
            assert editor.text == "A clue"
            editor.selection = Selection((0, 0), (0, 0))
            await click(app, pilot, "#notes-heading")
            assert editor.text == "# A clue"

    asyncio.run(scenario())


def test_notes_are_saved_and_loaded(tmp_path):
    path = tmp_path / "markdown.json"
    notes = "# Ada\n\n**Keep** the map.\n"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            editor = app.query_one("#session-notes", TextArea)
            editor.load_text(notes)
            app.query_one("#session-name", Input).value = "Markdown campaign"
            app.query_one("#session-path", Input).value = str(path)
            await click(app, pilot, "#save-session")
            assert SavedSession.load(path).notes == notes
            editor.load_text("# Unsaved replacement")
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert editor.text == notes

    asyncio.run(scenario())
