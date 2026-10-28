import pytest
from helpers import active_tab, reveal, run_app, start_game
from textual.widgets import Input, TextArea

pytestmark = pytest.mark.ui


def test_edits_survive_switching_tabs_and_repeat_roll_still_works():
    async def scenario(app, pilot):
        assert active_tab(app) == "tab-character"
        assert app.query_one("#tab-character").query("#character-name")
        assert app.query_one("#tab-session").query("#session-notes")
        assert not app.query_one("#details").query("#fear")
        await start_game(app, pilot)
        app.query_one("#character-name", Input).value = "Ada"
        app.query_one("#session-notes", TextArea).load_text("Keep the map")
        await reveal(app, pilot, "#session-name")
        assert active_tab(app) == "tab-session"
        await pilot.press("ctrl+r")
        assert len(app.history) == 1
        await reveal(app, pilot, "#character-name")
        assert app.query_one("#character-name", Input).value == "Ada"
        assert app.query_one("#session-notes", TextArea).text == "Keep the map"

    run_app(scenario)
