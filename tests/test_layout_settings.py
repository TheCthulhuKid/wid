import pytest
from helpers import active_tab, collapsed, run_app

from wid.settings import Settings, load_settings, save_settings

pytestmark = pytest.mark.ui


def test_saved_layout_is_restored_on_start_without_rewriting_the_file(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(tab="session", strain_collapsed=True, items_collapsed=True), path)
    before = path.read_text(encoding="utf-8")

    async def scenario(app, pilot):
        assert active_tab(app) == "tab-session"
        assert collapsed(app, "strain") and collapsed(app, "items")

    run_app(scenario, size=(100, 45), settings_path=path)
    assert path.read_text(encoding="utf-8") == before


def test_layout_changes_are_saved_with_the_other_settings(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="nord"), path)

    async def scenario(app, pilot):
        app.theme = "dracula"
        await pilot.press("s", "t")
        await pilot.pause()

    run_app(scenario, size=(100, 45), settings_path=path)
    saved = load_settings(path)
    assert (saved.theme, saved.tab, saved.strain_collapsed, saved.items_collapsed) == (
        "dracula",
        "session",
        True,
        None,
    )


def test_a_small_terminal_starts_folded_without_saving_that(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        assert collapsed(app, "strain")
        assert not path.exists()

    run_app(scenario, size=(80, 24), settings_path=path)


def test_an_unwritable_settings_file_is_reported_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        await pilot.press("t")
        await pilot.pause()
        assert collapsed(app, "strain")
        assert "Could not save settings" in str(app.query_one("#feedback").content)

    run_app(scenario, size=(100, 45), settings_path=blocker / "settings.json")
