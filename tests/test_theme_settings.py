import asyncio

from textual.widgets import Static

from wid.settings import Settings, load_settings, save_settings
from wid.ui.app import RollerApp
from wid.ui.themes import DANGER, DANGER_THEME, HIGHLIGHT


def run(settings_path, scenario):
    async def main():
        app = RollerApp(settings_path=settings_path)
        async with app.run_test(size=(100, 40)) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def test_saved_theme_is_applied_and_an_unknown_one_ignored(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="gruvbox"), path)

    async def scenario(app, pilot):
        assert app.theme == "gruvbox"

    run(path, scenario)
    save_settings(Settings(theme="no-such-theme"), path)

    async def unknown(app, pilot):
        assert app.theme == DANGER_THEME

    run(path, unknown)


def test_changed_theme_is_saved_and_other_settings_survive(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "nord", "future": true}', encoding="utf-8")

    async def scenario(app, pilot):
        app.theme = "dracula"
        await pilot.pause()
        assert load_settings(path).theme == "dracula"

    run(path, scenario)


def test_unwritable_settings_are_reported_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        app.theme = "nord"
        await pilot.pause()
        assert app.theme == "nord"
        assert "Could not save settings" in str(app.query_one("#feedback", Static).content)

    run(blocker / "settings.json", scenario)


def test_character_sheet_theme_is_the_default(tmp_path):
    async def scenario(app, pilot):
        assert app.theme == DANGER_THEME
        assert app.available_themes[DANGER_THEME] is DANGER
        assert DANGER.primary == HIGHLIGHT == "#B22222"

    run(tmp_path / "settings.json", scenario)
