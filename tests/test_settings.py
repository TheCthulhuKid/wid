from wid.settings import Settings, load_settings, save_settings, settings_path


def test_settings_round_trip_and_create_their_folder(tmp_path):
    path = tmp_path / "nested" / "wid" / "settings.json"
    assert load_settings(path) == Settings()
    save_settings(Settings(theme="nord"), path)
    assert load_settings(path) == Settings(theme="nord")


def test_invalid_content_gives_defaults_and_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")
    assert load_settings(path) == Settings()
    path.write_text('{"theme": "nord", "future": true}', encoding="utf-8")
    assert load_settings(path) == Settings(theme="nord")


def test_path_follows_xdg_config_home_or_appdata_or_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert settings_path() == tmp_path / "xdg" / "wid" / "settings.json"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setattr("wid.settings.IS_WINDOWS", True)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert settings_path() == tmp_path / "Roaming" / "wid" / "settings.json"
    monkeypatch.setattr("wid.settings.IS_WINDOWS", False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert settings_path() == tmp_path / ".config" / "wid" / "settings.json"
