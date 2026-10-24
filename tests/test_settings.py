from pathlib import Path

import pytest

from wid.settings import Settings, load_settings, save_settings, settings_path


def test_missing_file_gives_defaults(tmp_path):
    assert load_settings(tmp_path / "none.json") == Settings()


def test_round_trip_creates_the_directory(tmp_path):
    path = tmp_path / "nested" / "wid" / "settings.json"

    save_settings(Settings(theme="nord"), path)

    assert load_settings(path) == Settings(theme="nord")


def test_save_replaces_the_previous_settings(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(theme="nord"), path)

    save_settings(Settings(theme="gruvbox"), path)

    assert load_settings(path).theme == "gruvbox"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", "", '{"theme": 3}', '{"theme": ["nord"]}', '{"theme": null'],
)
def test_invalid_content_gives_defaults(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")

    assert load_settings(path) == Settings()


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "nord", "future": true}', encoding="utf-8")

    assert load_settings(path) == Settings(theme="nord")


def test_unreadable_path_gives_defaults(tmp_path):
    assert load_settings(tmp_path) == Settings()


def test_save_to_an_impossible_location_raises(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    with pytest.raises(OSError):
        save_settings(Settings(theme="nord"), blocker / "settings.json")


def test_path_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert settings_path() == tmp_path / "wid" / "settings.json"


@pytest.mark.parametrize("value", [None, ""])
def test_path_falls_back_to_home_config(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("XDG_CONFIG_HOME")
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", value)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert settings_path() == tmp_path / ".config" / "wid" / "settings.json"


def test_default_path_is_isolated_from_the_real_home():
    assert not settings_path().is_relative_to(Path.home() / ".config")


def test_missing_home_directory_is_an_oserror(monkeypatch):
    def no_home():
        raise RuntimeError("no home")

    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr(Path, "home", no_home)

    with pytest.raises(OSError, match="home directory"):
        settings_path()
    assert load_settings() == Settings()
    with pytest.raises(OSError):
        save_settings(Settings(theme="nord"))
