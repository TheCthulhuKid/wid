import os
from pathlib import Path
from unittest.mock import patch

import pytest

from wid import selftest
from wid.cli import main

pytestmark = pytest.mark.ui


def test_every_check_passes_and_is_reported(capsys):
    assert selftest.run_self_test() == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "wid self-test passed"
    assert [line[5:] for line in lines[:-1]] == [name for name, _ in selftest.CHECKS]
    assert all(line.startswith("ok   ") for line in lines[:-1])


def test_a_failing_check_is_reported_and_the_others_still_run(capsys):
    async def broken(app, pilot, folder):
        selftest.require(False, "boom")

    async def crashing(app, pilot, folder):
        raise KeyError("missing")

    checks = (
        *selftest.CHECKS[:2],
        ("broken", broken),
        ("crashing", crashing),
        *selftest.CHECKS[2:],
    )
    with patch.object(selftest, "CHECKS", checks):
        assert selftest.run_self_test() == 1

    out = capsys.readouterr().out.splitlines()
    assert "FAIL broken - AssertionError: boom" in out
    assert "FAIL crashing - KeyError: 'missing'" in out
    assert out[-1] == "wid self-test FAILED (2)"
    assert sum(line.startswith("ok   ") for line in out) == len(selftest.CHECKS)


def test_the_check_leaves_the_users_config_folder_alone():
    config = Path(os.environ["XDG_CONFIG_HOME"])

    selftest.run_self_test()

    assert list(config.iterdir()) == []


def test_the_command_line_flag_runs_it_instead_of_the_app(capsys):
    with patch("wid.cli.RollerApp") as app, pytest.raises(SystemExit) as stop:
        main(["--self-test"])

    assert stop.value.code == 0
    assert "wid self-test passed" in capsys.readouterr().out
    app.assert_not_called()


def test_help_mentions_the_flag(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "--self-test" in capsys.readouterr().out
