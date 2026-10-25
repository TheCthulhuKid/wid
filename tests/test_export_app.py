import asyncio
from random import Random

from helpers import reveal
from test_rollerapp import start_game, text
from test_session_app import click_control
from textual.widgets import Input

from wid.ui.app import RollerApp
from wid.ui.dialogs import ExportHistory


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
    await click_control(app, pilot, "#export-history")
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
        assert "## 2. Roll" in content
        assert str(app.history[0]) in content
        assert text(app, "#feedback") == f"Exported 2 history entries to {target}."
        assert [p.name for p in tmp_path.iterdir()] == ["export.md"]

    run(scenario)


def test_the_dialog_offers_the_session_path_with_an_md_ending(tmp_path):
    async def scenario(app, pilot):
        await play(app, pilot)
        await reveal(app, pilot, "#session-path")
        app.query_one("#session-path", Input).value = str(tmp_path / "campaign.json")
        await click_control(app, pilot, "#export-history")
        assert app.screen.query_one("#export-path", Input).value == str(tmp_path / "campaign.md")

    run(scenario)


def test_the_dialog_offers_a_plain_name_without_a_session_path():
    async def scenario(app, pilot):
        await play(app, pilot)
        await click_control(app, pilot, "#export-history")
        assert app.screen.query_one("#export-path", Input).value == "history.md"

    run(scenario)


def test_a_session_path_without_a_file_name_falls_back_to_the_plain_name():
    async def scenario(app, pilot):
        await play(app, pilot)
        for value in ("/", ".", "..", "   "):
            await reveal(app, pilot, "#session-path")
            app.query_one("#session-path", Input).value = value
            await click_control(app, pilot, "#export-history")
            assert app.screen.query_one("#export-path", Input).value == "history.md", value
            await pilot.press("escape")
            await pilot.pause()

    run(scenario)


def test_nothing_to_export_before_anything_happened(tmp_path):
    async def scenario(app, pilot):
        screen = app.screen
        await click_control(app, pilot, "#export-history")
        assert app.screen is screen
        assert text(app, "#feedback") == "There is no history to export yet."

    run(scenario)


def test_cancelling_writes_nothing(tmp_path):
    async def scenario(app, pilot):
        await play(app, pilot)
        await click_control(app, pilot, "#export-history")
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ExportHistory)
        await click_control(app, pilot, "#export-history")
        await pilot.click("#cancel-export")
        await pilot.pause()
        assert not list(tmp_path.iterdir())

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
        assert text(app, "#feedback") == "Export canceled; existing file unchanged."
        await export_to(app, pilot, target)
        await pilot.click("#confirm-session")
        await pilot.pause()
        assert target.read_text(encoding="utf-8").startswith("# ")
        assert text(app, "#feedback").startswith("Exported 2 history entries")

    run(scenario)


def test_a_missing_folder_or_blank_path_is_reported_without_a_file(tmp_path):
    async def scenario(app, pilot):
        await play(app, pilot)
        await export_to(app, pilot, tmp_path / "missing" / "export.md")
        assert "Could not export history" in text(app, "#feedback")
        await export_to(app, pilot, "   ")
        assert text(app, "#feedback") == "Could not export history: Choose a history file path"
        assert not list(tmp_path.iterdir())
        assert len(app.history) == 2

    run(scenario)
