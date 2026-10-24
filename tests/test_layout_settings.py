import asyncio

import pytest
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


def test_new_settings_default_to_not_chosen():
    settings = Settings()

    assert (settings.tab, settings.strain_collapsed, settings.items_collapsed) == (None,) * 3


@pytest.mark.parametrize("content", ['{"strain_collapsed": "yes"}', '{"items_collapsed": 1}'])
def test_a_non_boolean_choice_makes_the_file_invalid(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")

    assert load_settings(path) == Settings()


def test_saved_layout_is_restored_on_start(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(tab="session", strain_collapsed=True, items_collapsed=True), path)

    async def scenario(app, pilot):
        assert tab(app) == "tab-session"
        assert collapsed(app, "strain") and collapsed(app, "items")

    run(path, scenario)


def test_saved_open_sections_beat_the_small_terminal_default(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(strain_collapsed=False), path)

    async def scenario(app, pilot):
        assert not collapsed(app, "strain")
        assert collapsed(app, "items")

    run(path, scenario, size=(80, 24))


def test_without_settings_the_terminal_size_decides(tmp_path):
    async def scenario(app, pilot):
        assert tab(app) == "tab-character"
        assert not collapsed(app, "strain") and not collapsed(app, "items")

    run(tmp_path / "settings.json", scenario)


def test_an_unknown_saved_tab_is_ignored(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(tab="somewhere"), path)

    async def scenario(app, pilot):
        assert tab(app) == "tab-character"

    run(path, scenario)


@pytest.mark.parametrize("size", [(100, 45), (80, 24)])
def test_starting_up_writes_nothing(tmp_path, size):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        await pilot.pause()
        assert not path.exists()

    run(path, scenario, size)


def test_restoring_a_saved_layout_does_not_rewrite_the_file(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(tab="session", items_collapsed=True), path)
    before = (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns)

    async def scenario(app, pilot):
        await pilot.pause()

    run(path, scenario)

    assert (path.read_text(encoding="utf-8"), path.stat().st_mtime_ns) == before


def test_switching_tab_is_saved(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        await pilot.press("s")
        await pilot.pause()
        assert load_settings(path).tab == "session"
        await pilot.press("c")
        await pilot.pause()
        assert load_settings(path).tab == "character"

    run(path, scenario)


def test_toggling_a_section_is_saved_and_the_other_stays_unchosen(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        await pilot.press("t")
        await pilot.pause()
        saved = load_settings(path)
        assert saved.strain_collapsed is True
        assert saved.items_collapsed is None
        await pilot.press("t")
        await pilot.pause()
        assert load_settings(path).strain_collapsed is False

    run(path, scenario)


def test_clicking_a_section_title_is_saved_too(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        await pilot.click("#items-section CollapsibleTitle")
        await pilot.pause()
        assert collapsed(app, "items")
        assert load_settings(path).items_collapsed is True

    run(path, scenario)


def test_a_small_terminal_default_is_only_saved_once_the_user_changes_it(tmp_path):
    path = tmp_path / "settings.json"

    async def scenario(app, pilot):
        assert collapsed(app, "strain")
        assert not path.exists()
        await pilot.press("t")
        await pilot.pause()
        assert load_settings(path).strain_collapsed is False

    run(path, scenario, size=(80, 24))


def test_other_settings_survive_layout_changes(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="nord"), path)

    async def scenario(app, pilot):
        await pilot.press("s", "t")
        await pilot.pause()
        saved = load_settings(path)
        assert (saved.theme, saved.tab, saved.strain_collapsed) == ("nord", "session", True)

    run(path, scenario)


def test_the_layout_carries_over_to_the_next_run(tmp_path):
    path = tmp_path / "settings.json"

    async def first(app, pilot):
        await pilot.press("s", "i")
        await pilot.pause()

    run(path, first)

    async def second(app, pilot):
        assert tab(app) == "tab-session"
        assert collapsed(app, "items")
        assert not collapsed(app, "strain")

    run(path, second)


def test_an_unwritable_settings_file_is_reported_not_fatal(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    async def scenario(app, pilot):
        await pilot.press("t")
        await pilot.pause()
        assert collapsed(app, "strain")
        assert "Could not save settings" in str(app.query_one("#feedback").content)

    run(blocker / "settings.json", scenario)
