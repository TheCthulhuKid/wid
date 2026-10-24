import runpy
import subprocess
import sys
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import pytest

from huckdeck.cli import main

PACKAGE = "huckdeck"
BLOCKED = "wid"


def test_module_entry_point_calls_cli_main():
    with patch(f"{PACKAGE}.cli.main") as main:
        runpy.run_module(PACKAGE, run_name="__main__")

    main.assert_called_once_with()


def test_package_import_does_not_load_application_dependencies():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                f"import sys; import {PACKAGE}; "
                f"assert not {{'{PACKAGE}.cli', '{PACKAGE}.ui.app', 'textual', 'pydantic'}} "
                "& sys.modules.keys()"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_applications_import_without_the_other_package():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib
import sys

class BlockPackage:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == {BLOCKED!r}:
            raise ImportError('Applications must not depend on each other')

sys.meta_path.insert(0, BlockPackage())
importlib.import_module({PACKAGE + ".cli"!r})
assert not any(name.split('.')[0] == {BLOCKED!r} for name in sys.modules)
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_ui_stylesheet_is_a_nonempty_package_resource():
    stylesheet = files("huckdeck.ui").joinpath("dealer.tcss")

    assert stylesheet.is_file()
    assert stylesheet.read_text(encoding="utf-8").strip()


def test_version_flag_prints_the_version_without_starting_the_app(capsys):
    with patch("huckdeck.cli.HuckDeck") as app, pytest.raises(SystemExit) as stop:
        main(["--version"])

    assert stop.value.code == 0
    assert capsys.readouterr().out == f"huckdeck {version('huckdeck')}\n"
    app.assert_not_called()


def test_unknown_arguments_are_refused(capsys):
    with patch("huckdeck.cli.HuckDeck") as app, pytest.raises(SystemExit) as stop:
        main(["--bogus"])

    assert stop.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    app.assert_not_called()
