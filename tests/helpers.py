import sys

import pytest
from textual.errors import NoWidget
from textual.widget import Widget
from textual.widgets import Collapsible, Select, TabbedContent, TabPane

from wid.ui.dialogs import ConfirmReset


async def reveal(app, pilot, selector: str) -> Widget:
    """Make a widget visible: activate its tab, expand its sections, and scroll to it.

    Widgets inside an inactive tab or a collapsed section exist and keep their values but
    have no screen region, so tests that click, focus or measure one must call this first.
    Under load the layout can take several refreshes to settle, so this waits until the widget
    is really at its place on screen, where a click lands on it and not on what was there.
    """
    widget = app.query_one(selector)
    for ancestor in reversed(widget.ancestors):
        if isinstance(ancestor, TabPane):
            tabs = next(a for a in ancestor.ancestors if isinstance(a, TabbedContent))
            tabs.active = ancestor.id
        elif isinstance(ancestor, Collapsible):
            ancestor.collapsed = False
    for _ in range(50):
        await pilot.pause()
        widget.scroll_visible(animate=False)
        await pilot.pause()
        if lands_on(app, widget):
            return widget
    raise AssertionError(f"{selector} never settled on screen")


def lands_on(app, widget: Widget) -> bool:
    """Whether a click at the widget's corner, where the pilot clicks, would reach it."""
    try:
        under, _ = app.get_widget_at(*widget.region.offset)
    except NoWidget:
        return False
    return widget in under.ancestors_with_self


async def click(app, pilot, selector: str) -> None:
    """Reveal a widget, click it, and let the app handle the click."""
    await reveal(app, pilot, selector)
    assert await pilot.click(selector), f"the click missed {selector}"
    await pilot.pause()


async def change_genre(app, pilot, genre) -> None:
    """Switch the genre kit, confirming the new game if the app asks."""
    app.query_one("#genre", Select).value = genre
    await pilot.pause()
    if isinstance(app.screen, ConfirmReset):
        await pilot.click("#confirm-reset")
        await pilot.pause()


# Windows has no POSIX permission bits, umask or ``~user`` lookup; tests of those are skipped there.
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only behaviour")
