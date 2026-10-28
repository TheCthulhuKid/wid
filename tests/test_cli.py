import runpy
import sys
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from unittest.mock import call, patch

import pytest

from wid.cli import main, package_version
from wid.gm import GmGame
from wid.settings import gm_recovery_path, recovery_path

ENTRY_SCRIPT = Path(__file__).resolve().parents[1] / "release" / "wid_entry.py"


def test_main_launches_roller_app():
    with patch("wid.ui.app.RollerApp") as app:
        main(["game.json"])

    app.assert_called_once_with(recovery_path=recovery_path(), open_path="game.json")
    app.return_value.run.assert_called_once_with()


def test_gm_flag_and_a_gm_file_launch_the_gm_app(tmp_path):
    gm_file = tmp_path / "gm.json"
    GmGame().saved_session("GM").save(gm_file)
    with patch("wid.ui.gm_app.GmApp") as app, patch("wid.ui.app.RollerApp") as roller:
        main(["--gm"])
        main([str(gm_file)])

    assert app.call_args_list == [
        call(recovery_path=gm_recovery_path(), open_path=None),
        call(recovery_path=gm_recovery_path(), open_path=str(gm_file)),
    ]
    roller.assert_not_called()


def test_installed_command_entry_point():
    entry_point = next(point for point in distribution("wid").entry_points if point.name == "wid")

    assert entry_point.group == "console_scripts"
    assert entry_point.load() is main


def test_version_flag_prints_the_installed_version_without_starting_the_app(capsys):
    with patch("wid.ui.app.RollerApp") as app, pytest.raises(SystemExit) as stop:
        main(["--version"])

    assert stop.value.code == 0
    assert capsys.readouterr().out == f"wid {version('wid')}\n"
    app.assert_not_called()
    with patch("wid.cli.version", side_effect=PackageNotFoundError):
        assert package_version() == "unknown"


def test_the_entry_script_for_release_builds_runs_the_same_main():
    entry = runpy.run_path(str(ENTRY_SCRIPT), run_name="not_main")

    assert entry["main"] is main
    with patch("wid.ui.app.RollerApp") as app, patch.object(sys, "argv", ["wid"]):
        runpy.run_path(str(ENTRY_SCRIPT), run_name="__main__")
    app.return_value.run.assert_called_once_with()
