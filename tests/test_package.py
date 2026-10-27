import runpy
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

PACKAGE = "wid"


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


def test_ui_stylesheet_is_a_nonempty_package_resource():
    stylesheet = files("wid.ui").joinpath("roller.tcss")

    assert stylesheet.is_file()
    assert stylesheet.read_text(encoding="utf-8").strip()
