import asyncio
from unittest.mock import patch

import pytest
from helpers import reveal
from test_rollerapp import start_game
from test_session_app import click_control, load_game
from textual.document._document import Selection
from textual.widgets import Button, Input, Markdown, TextArea

from wid.sessions import SavedSession
from wid.ui.app import RollerApp


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_notes_preview_preserves_source_and_fits_panel(size):
    notes = (
        "# Campaign 🎲\n\n**Danger** and *hope*\n\n- Keep the map\n- [Clue](https://example.com)"
    )

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            editor = app.query_one("#session-notes", TextArea)
            preview = app.query_one("#notes-preview", Markdown)
            panel = app.query_one("#notes-preview-panel")
            editor.load_text(notes)
            editor.move_cursor((2, 4))
            selection = editor.selection
            assert editor.display and not panel.display
            await click_control(app, pilot, "#toggle-notes-preview")
            assert not editor.display and panel.display
            assert preview.source == notes
            assert preview.query("MarkdownH1")
            assert preview.query("MarkdownBulletList")
            with patch.object(app, "open_url") as open_url:
                preview.post_message(Markdown.LinkClicked(preview, "https://example.com"))
                await pilot.pause()
                open_url.assert_not_called()
            assert app.query_one("#notes-bold", Button).disabled
            assert editor.text == notes
            toolbar = await reveal(app, pilot, "#notes-toolbar")
            for button in toolbar.query(Button):
                assert toolbar.content_region.contains_region(button.region)
                assert button.content_size.width >= len(str(button.label))
            toggle = await reveal(app, pilot, "#toggle-notes-preview")
            toggle.focus()
            await pilot.pause(0.4)
            await pilot.press("enter")
            assert editor.display and not panel.display
            assert editor.selection == selection
            assert app.focused is editor
            assert editor.text == notes
            assert not app.query_one("#notes-bold", Button).disabled
            editor.load_text("")
            await click_control(app, pilot, "#toggle-notes-preview")
            assert preview.source == ""

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("button", "source", "selection", "expected"),
    [
        ("bold", "A clue 🎲", ((0, 2), (0, 6)), "A **clue** 🎲"),
        ("italic", "A clue 🎲", ((0, 6), (0, 2)), "A *clue* 🎲"),
        ("bold", "", ((0, 0), (0, 0)), "**bold text**"),
        ("italic", "x", ((0, 1), (0, 1)), "x*italic text*"),
        ("heading", "a clue", ((0, 3), (0, 3)), "# a clue"),
        ("heading", "one\ntwo\nthree", ((0, 1), (2, 0)), "# one\n# two\nthree"),
        ("heading", "", ((0, 0), (0, 0)), "# "),
    ],
)
def test_notes_formatting_selection_cursor_and_undo(button, source, selection, expected):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            editor = app.query_one("#session-notes", TextArea)
            editor.load_text(source)
            editor.selection = Selection(*selection)
            await click_control(app, pilot, f"#notes-{button}")
            assert editor.text == expected
            assert app.focused is editor
            await pilot.press("ctrl+z")
            assert editor.text == source

    asyncio.run(scenario())


def test_save_and_load_markdown_while_previewing(tmp_path):
    path = tmp_path / "markdown.json"
    notes = "# Ada\n\n**Keep** the map.\n\n  Original whitespace.  \n"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            editor = app.query_one("#session-notes", TextArea)
            preview = app.query_one("#notes-preview", Markdown)
            editor.load_text(notes)
            await click_control(app, pilot, "#toggle-notes-preview")
            app.query_one("#session-name", Input).value = "Markdown campaign"
            app.query_one("#session-path", Input).value = str(path)
            await click_control(app, pilot, "#save-session")
            assert SavedSession.load(path).notes == notes
            editor.load_text("# Unsaved replacement")
            await pilot.pause()
            assert preview.source == editor.text
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            await pilot.pause()
            assert preview.source == editor.text == "# Unsaved replacement"
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert editor.text == preview.source == notes
            assert app.query_one("#notes-preview-panel").display
            legacy = SavedSession.load(path).model_dump_json(exclude={"notes"})
            path.write_text(legacy, encoding="utf-8")
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert editor.text == preview.source == ""

    asyncio.run(scenario())


def test_notes_toolbar_is_above_the_editor():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 45)) as pilot:
            await start_game(app, pilot)
            toolbar = await reveal(app, pilot, "#notes-toolbar")
            assert toolbar.region.y < app.query_one("#session-notes").region.y

    asyncio.run(scenario())
