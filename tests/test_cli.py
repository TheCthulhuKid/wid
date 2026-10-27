import asyncio
import runpy
import sys
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from unittest.mock import patch

import pytest

from wid.cli import main, package_version
from wid.settings import recovery_path
from wid.ui.app import RollerApp

ENTRY_SCRIPT = Path(__file__).resolve().parents[1] / "release" / "wid_entry.py"


def test_main_launches_roller_app():
    with patch("wid.ui.app.RollerApp") as app:
        main(["game.json"])

    app.assert_called_once_with(recovery_path=recovery_path(), open_path="game.json")
    app.return_value.run.assert_called_once_with()


def test_installed_command_entry_point():
    entry_point = next(point for point in distribution("wid").entry_points if point.name == "wid")

    assert entry_point.group == "console_scripts"
    assert entry_point.load() is main


@pytest.mark.ui
def test_app_starts_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        app = RollerApp()
        async with app.run_test():
            assert app.query_one("#genre")
            assert all(app.query_one(f"#roll-attribute-{index}").disabled for index in range(3))

    asyncio.run(scenario())


def test_version_flag_prints_the_installed_version_without_starting_the_app(capsys):
    with patch("wid.ui.app.RollerApp") as app, pytest.raises(SystemExit) as stop:
        main(["--version"])

    assert stop.value.code == 0
    assert capsys.readouterr().out == f"wid {version('wid')}\n"
    app.assert_not_called()


def test_version_is_unknown_when_the_package_is_not_installed():
    with patch("wid.cli.version", side_effect=PackageNotFoundError):
        assert package_version() == "unknown"


def test_help_describes_the_program(capsys):
    with patch("wid.ui.app.RollerApp") as app, pytest.raises(SystemExit) as stop:
        main(["--help"])

    assert stop.value.code == 0
    assert "dice roller" in capsys.readouterr().out
    app.assert_not_called()


def test_unknown_arguments_are_refused(capsys):
    with patch("wid.ui.app.RollerApp") as app, pytest.raises(SystemExit) as stop:
        main(["--bogus"])

    assert stop.value.code == 2
    assert "unrecognized arguments: --bogus" in capsys.readouterr().err
    app.assert_not_called()


def test_the_entry_script_for_release_builds_runs_the_same_main():
    entry = runpy.run_path(str(ENTRY_SCRIPT), run_name="not_main")

    assert entry["main"] is main
    with patch("wid.ui.app.RollerApp") as app, patch.object(sys, "argv", ["wid"]):
        runpy.run_path(str(ENTRY_SCRIPT), run_name="__main__")
    app.return_value.run.assert_called_once_with()
