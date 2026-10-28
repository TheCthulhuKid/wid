import asyncio

import pytest

from wid.settings import Settings, save_settings
from wid.ui.app import RollerApp
from wid.ui.themes import DANGER_THEME

pytestmark = pytest.mark.ui


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
