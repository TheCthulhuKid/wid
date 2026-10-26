import os
from pathlib import Path
from unittest.mock import patch

import pytest

from wid import selftest
from wid.cli import main

pytestmark = pytest.mark.ui


def test_every_check_passes_without_touching_the_users_config(capsys):
    assert selftest.run_self_test() == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "wid self-test passed"
    assert [line[5:] for line in lines[:-1]] == [name for name, _ in selftest.CHECKS]
    assert list(Path(os.environ["XDG_CONFIG_HOME"]).iterdir()) == []


def test_a_failing_check_is_reported(capsys):
    async def broken(app, pilot, folder):
        selftest.require(False, "boom")

    with patch.object(selftest, "CHECKS", (("broken", broken),)):
        assert selftest.run_self_test() == 1

    out = capsys.readouterr().out.splitlines()
    assert out == ["FAIL broken - AssertionError: boom", "wid self-test FAILED (1)"]


def test_the_command_line_flag_runs_it_instead_of_the_app():
    with (
        patch("wid.ui.app.RollerApp") as app,
        patch.object(selftest, "run_self_test", return_value=0) as run,
        pytest.raises(SystemExit) as stop,
    ):
        main(["--self-test"])

    assert stop.value.code == 0
    run.assert_called_once()
    app.assert_not_called()
