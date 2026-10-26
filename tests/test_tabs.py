import asyncio

from helpers import reveal
from test_rollerapp import start_game
from textual.widgets import Input, TabbedContent, TextArea

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
        assert app.query_one("#tab-character").query("#character-name")
        assert app.query_one("#tab-session").query("#session-notes")
        assert not app.query_one("#details").query("#fear")

    run(scenario)


def test_edits_survive_switching_tabs_and_repeat_roll_still_works():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        app.query_one("#character-name", Input).value = "Ada"
        app.query_one("#session-notes", TextArea).load_text("Keep the map")
        await reveal(app, pilot, "#session-name")
        assert tabs(app).active == "tab-session"
        await pilot.press("ctrl+r")
        assert len(app.history) == 1
        await reveal(app, pilot, "#character-name")
        assert app.query_one("#character-name", Input).value == "Ada"
        assert app.query_one("#session-notes", TextArea).text == "Keep the map"

    run(scenario)
