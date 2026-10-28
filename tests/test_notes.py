import asyncio

import pytest
from helpers import click
from textual.document._document import Selection
from textual.widgets import Markdown, TextArea

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_formatting_buttons_wrap_the_selection_and_preview_keeps_the_source():
    notes = "# Campaign 🎲\n\n**Danger** and *hope*\n\n- Keep the map"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 35)) as pilot:
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
