import asyncio

from textual.widgets import Collapsible, TabbedContent

from wid.settings import Settings, load_settings, save_settings
from wid.ui.app import RollerApp


def run(settings_path, scenario, size=(100, 45)):
    async def main():
        app = RollerApp(settings_path=settings_path)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await scenario(app, pilot)

    asyncio.run(main())


def tab(app):
    return app.query_one("#details", TabbedContent).active


def collapsed(app, name):
    return app.query_one(f"#{name}-section", Collapsible).collapsed


def test_saved_layout_is_restored_on_start_without_rewriting_the_file(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(tab="session", strain_collapsed=True, items_collapsed=True), path)
    before = path.read_text(encoding="utf-8")

    async def scenario(app, pilot):
        assert tab(app) == "tab-session"
        assert collapsed(app, "strain") and collapsed(app, "items")

    run(path, scenario)
    assert path.read_text(encoding="utf-8") == before


def test_layout_changes_are_saved_with_the_other_settings(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="nord"), path)

    async def scenario(app, pilot):
        await pilot.press("s", "t")
        await pilot.pause()

    run(path, scenario)
    saved = load_settings(path)
    assert (saved.theme, saved.tab, saved.strain_collapsed, saved.items_collapsed) == (
        "nord",
        "session",
        True,
        None,
    )


def test_a_small_terminal_starts_folded_without_saving_that(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        assert collapsed(app, "strain")
        assert not path.exists()

    run(path, scenario, size=(80, 24))


def test_an_unwritable_settings_file_is_reported_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        await pilot.press("t")
        await pilot.pause()
        assert collapsed(app, "strain")
        assert "Could not save settings" in str(app.query_one("#feedback").content)

    run(blocker / "settings.json", scenario)
