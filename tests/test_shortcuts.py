import asyncio

import pytest
from helpers import reveal
from test_rollerapp import start_game
from textual.widgets import Footer, Input, Select, TabbedContent
from textual.widgets.tabbed_content import ContentTabs

from wid.profiles import Genre
from wid.ui.app import RollerApp


def run(scenario, size=(100, 45)):
    async def main():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def active_tab(app):
    return app.query_one("#details", TabbedContent).active


async def tab_order(app, pilot, start, presses=80):
    """Ids of the widgets focused by pressing Tab from ``start`` (class name if it has no id)."""
    app.query_one(start).focus()
    seen = []
    for _ in range(presses):
        await pilot.press("tab")
        seen.append(app.focused.id or type(app.focused).__name__)
    return seen


def test_c_and_s_switch_tabs_and_focus_the_tab_bar():
    async def scenario(app, pilot):
        app.query_one("#fear", Select).focus()
        await pilot.press("s")
        await pilot.pause()
        assert active_tab(app) == "tab-session"
        assert isinstance(app.focused, ContentTabs)
        await pilot.press("c")
        await pilot.pause()
        assert active_tab(app) == "tab-character"
        assert isinstance(app.focused, ContentTabs)

    run(scenario)


def test_shortcuts_can_be_chained_and_one_tab_press_enters_the_tab():
    async def scenario(app, pilot):
        await pilot.press("s", "c", "s", "t", "i", "i", "t")
        await pilot.pause()
        assert active_tab(app) == "tab-session"
        assert not app.query_one("#strain-section").collapsed
        assert not app.query_one("#items-section").collapsed
        await pilot.press("s", "tab")
        assert app.focused.id == "session-name"
        await pilot.press("a")
        assert app.query_one("#session-name", Input).value == "a"

    run(scenario)


def test_arrow_keys_on_the_tab_bar_switch_tabs():
    async def scenario(app, pilot):
        await pilot.press("c")
        await pilot.press("right")
        await pilot.pause()
        assert active_tab(app) == "tab-session"
        await pilot.press("left")
        await pilot.pause()
        assert active_tab(app) == "tab-character"

    run(scenario)


def test_letters_are_typed_not_treated_as_shortcuts_inside_a_text_field():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).focus()
        await pilot.press("c", "s", "t", "i", "d")
        assert app.query_one("#character-name", Input).value == "cstid"
        assert active_tab(app) == "tab-character"
        assert not app.query_one("#strain-section").collapsed
        assert not app.query_one("#items-section").collapsed

    run(scenario)


def test_t_collapses_the_strain_section_and_moves_focus_out_of_it():
    async def scenario(app, pilot):
        (await reveal(app, pilot, "#take-strain")).focus()
        await pilot.press("t")
        await pilot.pause()
        assert app.query_one("#strain-section").collapsed
        assert type(app.focused).__name__ == "CollapsibleTitle"
        assert app.focused.region.width > 0
        await pilot.press("t")
        await pilot.pause()
        assert not app.query_one("#strain-section").collapsed

    run(scenario)


def test_i_toggles_the_items_section():
    async def scenario(app, pilot):
        app.query_one("#fear", Select).focus()
        await pilot.press("i")
        await pilot.pause()
        assert app.query_one("#items-section").collapsed
        assert app.query_one("#item-target").region.width == 0
        await pilot.press("i")
        await pilot.pause()
        assert not app.query_one("#items-section").collapsed

    run(scenario)


def test_shortcuts_do_nothing_while_a_confirmation_is_open():
    async def scenario(app, pilot):
        app.session.strain = app.session.strain.take(1)
        app.query_one("#genre", Select).value = Genre.HECKBOY
        await pilot.pause()
        dialog = app.screen
        await pilot.press("c", "s", "t", "i")
        assert app.screen is dialog
        await pilot.click("#cancel-reset")
        await pilot.pause()
        assert active_tab(app) == "tab-character"
        assert not app.query_one("#strain-section").collapsed
        assert not app.query_one("#items-section").collapsed

    run(scenario)


@pytest.mark.parametrize(
    "target",
    [
        "#session-name",
        "#session-notes",
        "#session-path",
        "#save-session",
        "#strain-box-0",
        "#strain-name-0",
        "#take-strain",
        "#name-appropriate_item",
        "#item-target",
        "#fear",
        "#character-looks",
        "#toggle-history",
    ],
)
def test_repeat_roll_works_from_every_area(target):
    async def scenario(app, pilot):
        await start_game(app, pilot)
        widget = await reveal(app, pilot, target)
        widget.focus()
        before = len(app.history)
        await pilot.press("ctrl+r")
        assert len(app.history) == before + 1, target

    run(scenario)


def test_tab_order_follows_the_screen_from_top_to_bottom():
    async def scenario(app, pilot):
        seen = await tab_order(app, pilot, "#genre")
        order = [
            "start-game",
            "load-session",
            "ContentTabs",
            "character-name",
            "attribute-rank-0",
            "fear",
            "assisted",
            "expertise",
            "CollapsibleTitle",
            "strain-box-0",
        ]
        positions = [seen.index(item) for item in order]
        assert positions == sorted(positions), list(zip(order, positions, strict=True))
        assert "session-name" not in seen
        assert seen.index("genre") > positions[-1]  # the cycle returns to the top

    run(scenario)


def test_tab_never_lands_on_a_widget_in_a_hidden_tab_or_section():
    async def scenario(app, pilot):
        app.query_one("#details", TabbedContent).active = "tab-session"
        app.query_one("#strain-section").collapsed = True
        app.query_one("#items-section").collapsed = True
        await pilot.pause()
        app.query_one("#genre").focus()
        for _ in range(80):
            await pilot.press("tab")
            assert app.focused.region.width > 0, app.focused.id
            assert not (app.focused.id or "").startswith(("character-", "strain-box"))

    run(scenario)


def test_focus_is_not_left_in_a_tab_that_is_switched_away():
    async def scenario(app, pilot):
        app.query_one("#character-name", Input).focus()
        app.query_one("#details", TabbedContent).active = "tab-session"
        await pilot.pause()
        assert app.focused is None or app.focused.region.width > 0

    run(scenario)


@pytest.mark.parametrize("width", [80, 100, 140])
def test_footer_lists_every_shortcut(width):
    async def scenario(app, pilot):
        await pilot.pause()
        footer = "".join(strip.text for strip in app.screen._compositor.render_strips()[-1:])
        for label in ("Theme", "Character", "Session", "Strain", "Items", "Repeat", "Log"):
            assert label in footer, (width, label)
        assert app.query_one(Footer).compact == (width < 90)

    run(scenario, (width, 24))
