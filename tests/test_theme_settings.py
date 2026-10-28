import pytest
from helpers import run_app

from wid.settings import Settings, save_settings
from wid.ui.themes import DANGER_THEME

pytestmark = pytest.mark.ui


def test_saved_theme_is_applied_and_an_unknown_one_ignored(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="gruvbox"), path)

    async def scenario(app, pilot):
        assert app.theme == "gruvbox"

    run_app(scenario, settings_path=path)
    save_settings(Settings(theme="no-such-theme"), path)

    async def unknown(app, pilot):
        assert app.theme == DANGER_THEME

    run_app(unknown, settings_path=path)
