import asyncio

import pytest
from helpers import reveal
from test_rollerapp import start_game
from test_session_app import click_control, load_game
from textual.widgets import Button, Input, Markdown, TabbedContent, TextArea

from wid.sessions import CharacterDetails, SavedSession
from wid.ui.app import RollerApp


def tabs(app):
    return app.query_one("#details", TabbedContent)


def run(scenario, size=(100, 40)):
    async def main():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def test_character_and_session_areas_are_in_their_own_tabs():
    async def scenario(app, pilot):
        assert tabs(app).active == "tab-character"
        character = app.query_one("#tab-character")
        session = app.query_one("#tab-session")
        character_widgets = (
            "#character-name",
            "#character-looks",
            "#character-nature",
            "#attribute-rank-0",
            "#roll-attribute-0",
            "#attribute-instructions",
        )
        for selector in character_widgets:
            assert character.query(selector), selector
        session_widgets = (
            "#session-name",
            "#session-notes",
            "#toggle-notes-preview",
            "#session-path",
            "#save-session",
        )
        for selector in session_widgets:
            assert session.query(selector), selector
        play_area = ("#genre", "#start-game", "#load-session", "#fear", "#assisted", "#take-strain")
        for selector in play_area:
            assert not app.query_one("#details").query(selector), selector

    run(scenario)


def test_character_tab_is_the_first_thing_under_the_game_row():
    async def scenario(app, pilot):
        row = app.query_one("#profile-fields")
        bar = app.query_one("#details Tabs")
        assert bar.region.y == row.region.bottom
        assert app.query_one("#character-name").region.y < app.query_one("#fear").region.y
        assert app.query_one("#roll-attribute-0").region.y < app.query_one("#fear").region.y

    run(scenario, (100, 40))


def test_repeat_roll_works_while_the_roll_buttons_are_hidden():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        await pilot.press("ctrl+r")
        first = app.session.current_result
        await reveal(app, pilot, "#session-name")
        assert tabs(app).active == "tab-session"
        assert app.query_one("#roll-attribute-0", Button).region.width == 0
        await pilot.press("ctrl+r")
        assert app.session.current_result is not first
        assert len(app.history) == 2

    run(scenario)


def test_edits_survive_switching_tabs():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).value = "Ada"
        app.query_one("#session-notes", TextArea).load_text("Keep the map")
        await reveal(app, pilot, "#session-name")
        assert tabs(app).active == "tab-session"
        app.query_one("#session-name", Input).value = "Friday"
        await reveal(app, pilot, "#character-name")
        assert tabs(app).active == "tab-character"
        assert app.query_one("#character-name", Input).value == "Ada"
        assert app.query_one("#session-notes", TextArea).text == "Keep the map"
        assert app.query_one("#session-name", Input).value == "Friday"

    run(scenario)


def test_load_fills_both_tabs_while_one_is_hidden(tmp_path, saved_session_factory):
    path = tmp_path / "loaded.json"
    saved = saved_session_factory().model_copy(
        update={
            "name": "Loaded game",
            "notes": "# Plan",
            "character": CharacterDetails(name="Ada", looks="Tall", nature="Brave"),
        }
    )
    saved.save(path)

    async def scenario(app, pilot):
        await reveal(app, pilot, "#session-path")
        app.query_one("#session-path", Input).value = str(path)
        assert tabs(app).active == "tab-session"
        await load_game(app, pilot)
        assert tabs(app).active == "tab-session"
        assert app.query_one("#character-name", Input).value == "Ada"
        assert app.query_one("#character-looks", Input).value == "Tall"
        assert app.query_one("#session-notes", TextArea).text == "# Plan"
        assert app.query_one("#session-name", Input).value == "Loaded game"
        await reveal(app, pilot, "#character-nature")
        assert app.query_one("#character-nature", Input).value == "Brave"

    run(scenario)


def test_save_includes_edits_made_in_the_other_tab(tmp_path):
    path = tmp_path / "saved.json"

    async def scenario(app, pilot):
        await start_game(app, pilot)
        app.query_one("#character-name", Input).value = "Ada"
        app.query_one("#session-notes", TextArea).load_text("Notes")
        await reveal(app, pilot, "#session-name")
        app.query_one("#session-name", Input).value = "Friday"
        app.query_one("#session-path", Input).value = str(path)
        await click_control(app, pilot, "#save-session")
        saved = SavedSession.load(path)
        assert saved.name == "Friday"
        assert saved.character.name == "Ada"
        assert saved.notes == "Notes"

    run(scenario)


def test_notes_preview_stays_on_across_tab_switches():
    async def scenario(app, pilot):
        app.query_one("#session-notes", TextArea).load_text("# Heading\n\n- item")
        await click_control(app, pilot, "#toggle-notes-preview")
        assert app.query_one("#notes-preview-panel").display
        assert not app.query_one("#session-notes").display
        await reveal(app, pilot, "#character-name")
        assert tabs(app).active == "tab-character"
        await reveal(app, pilot, "#toggle-notes-preview")
        assert tabs(app).active == "tab-session"
        assert app.query_one("#notes-preview-panel").display
        assert str(app.query_one("#toggle-notes-preview", Button).label) == "Edit"
        assert app.query_one("#notes-preview", Markdown).query("MarkdownH1")

    run(scenario)


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_both_tabs_fit_the_configuration_panel(size):
    async def scenario(app, pilot):
        configuration = app.query_one("#configuration")
        for target in ("#character-name", "#session-name"):
            field = await reveal(app, pilot, target)
            assert configuration.content_region.contains_region(field.region)
            assert field.region.width >= 15  # as wide as before the tabs existed
        bar = app.query_one("#details Tabs")
        bar.scroll_visible(animate=False)
        await pilot.pause()
        assert configuration.content_region.contains_region(bar.region)

    run(scenario, size)
