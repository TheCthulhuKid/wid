import sys

import pytest
from textual.widget import Widget
from textual.widgets import Collapsible, TabbedContent, TabPane


async def reveal(app, pilot, selector: str) -> Widget:
    """Make a widget visible: activate its tab, expand its sections, and scroll to it.

    Widgets inside an inactive tab or a collapsed section exist and keep their values but
    have no screen region, so tests that click, focus or measure one must call this first.
    """
    widget = app.query_one(selector)
    for ancestor in reversed(widget.ancestors):
        if isinstance(ancestor, TabPane):
            tabs = next(a for a in ancestor.ancestors if isinstance(a, TabbedContent))
            tabs.active = ancestor.id
        elif isinstance(ancestor, Collapsible):
            ancestor.collapsed = False
    await pilot.pause()
    widget.scroll_visible(animate=False)
    await pilot.pause()
    return widget


# Windows has no POSIX permission bits, umask or ``~user`` lookup; tests of those are skipped there.
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only behaviour")
