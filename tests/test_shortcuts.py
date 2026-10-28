import asyncio

import pytest
from textual.widgets import Input, Select, TabbedContent
from textual.widgets.tabbed_content import ContentTabs

from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def run(scenario, size=(100, 45)):
    async def main():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def active_tab(app):
    return app.query_one("#details", TabbedContent).active


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

    run(scenario)


def test_letters_are_typed_inside_a_text_field():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).focus()
        await pilot.press("c", "s", "t")
        assert app.query_one("#character-name", Input).value == "cst"
        assert not app.query_one("#strain-section").collapsed

    run(scenario)
