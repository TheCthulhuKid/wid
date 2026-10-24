import asyncio

from textual.widgets import Static

from wid.settings import Settings, load_settings, save_settings
from wid.ui.app import RollerApp


def run(settings_path, scenario):
    async def main():
        app = RollerApp(settings_path=settings_path)
        async with app.run_test(size=(100, 40)) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def test_saved_theme_is_applied_on_start(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="gruvbox"), path)

    async def scenario(app, pilot):
        assert app.theme == "gruvbox"

    run(path, scenario)


def test_unknown_saved_theme_is_ignored(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="no-such-theme"), path)

    async def scenario(app, pilot):
        assert app.theme == "textual-dark"

    run(path, scenario)


def test_nothing_is_written_until_the_theme_changes(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        await pilot.pause()
        assert not path.exists()

    run(path, scenario)


def test_changed_theme_is_saved_and_other_settings_survive(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "nord", "future": true}', encoding="utf-8")

    async def scenario(app, pilot):
        app.theme = "dracula"
        await pilot.pause()
        assert load_settings(path).theme == "dracula"

    run(path, scenario)


def test_default_location_is_used_without_an_explicit_path():
    async def scenario(app, pilot):
        app.theme = "monokai"
        await pilot.pause()
        assert load_settings().theme == "monokai"

    run(None, scenario)


def test_unwritable_settings_are_reported_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        app.theme = "nord"
        await pilot.pause()
        assert app.theme == "nord"
        assert "Could not save settings" in str(app.query_one("#feedback", Static).content)

    run(blocker / "settings.json", scenario)


def test_failed_save_from_the_theme_picker_is_reported(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        await pilot.press("d")
        await pilot.pause()
        await pilot.press(*"nord")
        await pilot.pause(0.5)
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme == "nord"
        assert "Could not save settings" in str(app.query_one("#feedback", Static).content)

    run(blocker / "settings.json", scenario)
