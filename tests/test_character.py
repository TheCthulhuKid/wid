import asyncio

import pytest
from helpers import click, load_game, start_game
from textual.widgets import Input

from wid.sessions import CharacterDetails, SavedSession
from wid.ui.app import RollerApp

pytestmark = pytest.mark.ui


def test_character_details_are_saved_and_loaded(tmp_path):
    path = tmp_path / "character.json"
    details = {"name": "Ada 🎲", "looks": "Red coat", "nature": "Curious"}

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for field, value in details.items():
                app.query_one(f"#character-{field}", Input).value = value
            await start_game(app, pilot)
            app.query_one("#session-name", Input).value = "Campaign"
            app.query_one("#session-path", Input).value = str(path)
            await click(app, pilot, "#save-session")
            assert SavedSession.load(path).character == CharacterDetails(**details)

        loaded = RollerApp()
        async with loaded.run_test(size=(100, 40)) as pilot:
            loaded.query_one("#session-path", Input).value = str(path)
            await load_game(loaded, pilot)
            for field, value in details.items():
                assert loaded.query_one(f"#character-{field}", Input).value == value

    asyncio.run(scenario())
