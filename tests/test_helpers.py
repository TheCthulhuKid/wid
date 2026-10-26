import asyncio

from helpers import reveal
from textual.app import App
from textual.widgets import Checkbox, Collapsible, Input, TabbedContent, TabPane


class Sample(App):
    def compose(self):
        yield Input(id="plain")
        with TabbedContent(initial="first"):
            with TabPane("First", id="first"):
                yield Input(id="in-first")
            with TabPane("Second", id="second"):
                yield Input(id="in-second")
                with Collapsible(title="More", collapsed=True):
                    yield Checkbox("Deep", id="deep")


def run(selector, check):
    async def scenario():
        app = Sample()
        async with app.run_test(size=(60, 20)) as pilot:
            widget = await reveal(app, pilot, selector)
            check(app, widget)

    asyncio.run(scenario())


def test_reveal_activates_the_tab_and_expands_the_section():
    def check(app, widget):
        assert app.query_one(TabbedContent).active == "second"
        assert not app.query_one(Collapsible).collapsed
        assert widget.region.width > 0

    run("#deep", check)
