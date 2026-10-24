import asyncio
from importlib.metadata import distribution
from unittest.mock import patch

from wid.cli import main
from wid.ui.app import RollerApp


def test_main_launches_roller_app():
    with patch("wid.cli.RollerApp") as app:
        main()

    app.assert_called_once_with()
    app.return_value.run.assert_called_once_with()


def test_installed_command_entry_point():
    entry_point = next(point for point in distribution("wid").entry_points if point.name == "wid")

    assert entry_point.group == "console_scripts"
    assert entry_point.load() is main


def test_app_starts_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        app = RollerApp()
        async with app.run_test():
            assert app.query_one("#genre")
            assert all(app.query_one(f"#roll-attribute-{index}").disabled for index in range(3))

    asyncio.run(scenario())
