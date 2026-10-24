import asyncio

import pytest
from test_rollerapp import start_game, text
from textual.widgets import Button, Input, Select

from wid.ui.app import RollerApp


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_load_game_is_beside_start_and_remains_available(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            start = app.query_one("#start-game", Button)
            load = app.query_one("#load-session", Button)
            genre = app.query_one("#genre", Select)
            assert str(load.label) == "Load game"
            assert load.region.y == start.region.y == genre.region.y
            assert load.region.x >= start.region.right
            assert genre.region.width >= 16
            assert app.query_one("#configuration").content_region.contains_region(load.region)
            await start_game(app, pilot)
            assert load.display and not load.disabled
            assert not start.display
            assert await pilot.click(load)
            await pilot.pause()
            assert app.screen.query_one("#load-path", Input).has_focus
            await pilot.press("escape")
            assert app.session.attributes is not None

    asyncio.run(scenario())


def test_prompt_loads_path_without_setup(tmp_path, saved_session_factory):
    path = tmp_path / "campaign.json"
    saved = saved_session_factory()
    saved.save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            assert await pilot.click("#load-session")
            await pilot.pause()
            editor = app.screen.query_one("#load-path", Input)
            assert editor.has_focus
            editor.value = str(path)
            await pilot.press("enter")
            await pilot.pause()
            assert app.session.model_dump() == saved.session.model_dump()
            assert app.query_one("#session-path", Input).value == str(path)
            assert app.query_one("#load-session", Button).display
            assert all(
                not app.query_one(f"#roll-attribute-{index}", Button).disabled for index in range(3)
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", ["escape", "button"])
def test_prompt_cancel_preserves_game_and_path(tmp_path, cancel):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            app.query_one("#session-path", Input).value = str(tmp_path / "original.json")
            before = app.session.model_dump()
            await pilot.click("#load-session")
            await pilot.pause()
            editor = app.screen.query_one("#load-path", Input)
            assert editor.value.endswith("original.json")
            editor.value = str(tmp_path / "different.json")
            if cancel == "escape":
                await pilot.press("escape")
            else:
                await pilot.click("#cancel-load")
            await pilot.pause()
            assert app.session.model_dump() == before
            assert app.query_one("#session-path", Input).value.endswith("original.json")

    asyncio.run(scenario())


def test_blank_and_missing_paths_keep_game(tmp_path):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            before = app.session.model_dump()
            for path in (" ", str(tmp_path / "missing.json")):
                await pilot.click("#load-session")
                await pilot.pause()
                app.screen.query_one("#load-path", Input).value = path
                await pilot.click("#submit-load")
                await pilot.pause()
                assert "Could not load session" in text(app, "#feedback")
                assert app.session.model_dump() == before

    asyncio.run(scenario())
