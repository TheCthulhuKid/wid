import pytest
from helpers import active_tab, run_app
from textual.widgets import Input, Select
from textual.widgets.tabbed_content import ContentTabs

pytestmark = pytest.mark.ui


def test_letter_shortcuts_switch_tabs_and_fold_sections():
    async def scenario(app, pilot):
        app.query_one("#fear", Select).focus()
        await pilot.press("s")
        await pilot.pause()
        assert active_tab(app) == "tab-session"
        assert isinstance(app.focused, ContentTabs)
        await pilot.press("c", "t", "i")
        await pilot.pause()
        assert active_tab(app) == "tab-character"
        assert app.query_one("#strain-section").collapsed
        assert app.query_one("#items-section").collapsed

    run_app(scenario, size=(100, 45))


def test_letters_are_typed_inside_a_text_field():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).focus()
        await pilot.press("c", "s", "t")
        assert app.query_one("#character-name", Input).value == "cst"
        assert not app.query_one("#strain-section").collapsed

    run_app(scenario, size=(100, 45))
