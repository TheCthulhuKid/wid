import asyncio
from random import Random

import pytest
from helpers import click, start_game, text
from textual.widgets import Input

from wid.ui.app import RollerApp
from wid.ui.dialogs import ExportHistory

pytestmark = pytest.mark.ui


def run(scenario, size=(100, 45)):
    async def main():
        app = RollerApp(rng=Random(5))
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


async def play(app, pilot, rolls=2):
    await start_game(app, pilot)
    for _ in range(rolls):
        await pilot.press("ctrl+r")


async def export_to(app, pilot, path):
    await click(app, pilot, "#export-history")
    assert isinstance(app.screen, ExportHistory)
    app.screen.query_one("#export-path", Input).value = str(path)
    await pilot.click("#submit-export")
    await pilot.pause()


def test_exports_the_history_to_a_markdown_file(tmp_path):
    target = tmp_path / "export.md"

    async def scenario(app, pilot):
        await play(app, pilot)
        app.query_one("#session-name", Input).value = "Friday"
        app.query_one("#character-name", Input).value = "Ada"
        await export_to(app, pilot, target)
        content = target.read_text(encoding="utf-8")
        assert content.startswith("# Friday\n\nCharacter: Ada\n\n## 1. Roll\n")
        assert text(app, "#feedback") == f"Exported 2 history entries to {target}."

    run(scenario)


def test_an_existing_file_is_replaced_only_after_confirmation(tmp_path):
    target = tmp_path / "export.md"
    target.write_text("keep me", encoding="utf-8")

    async def scenario(app, pilot):
        await play(app, pilot)
        await export_to(app, pilot, target)
        await pilot.click("#cancel-session")
        await pilot.pause()
        assert target.read_text(encoding="utf-8") == "keep me"
        await export_to(app, pilot, target)
        await pilot.click("#confirm-session")
        await pilot.pause()
        assert target.read_text(encoding="utf-8").startswith("# ")

    run(scenario)
