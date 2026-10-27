import socket
from unittest.mock import patch

import pytest

from wid.cli import main
from wid.web import server


def run_serve(**options):
    """Serve with uvicorn and the browser mocked.

    Returns the exit code, the addresses the server was given (read while it "runs", since the
    socket is closed afterwards), and the browser mock.
    """
    addresses = []
    with (
        patch.object(server.uvicorn, "Server") as uvicorn_server,
        patch.object(server.webbrowser, "open") as browser,
    ):
        uvicorn_server.return_value.run.side_effect = lambda sockets: addresses.extend(
            sock.getsockname() for sock in sockets
        )
        code = server.serve(**options)
    return code, addresses, browser


def test_serves_on_the_loopback_address_and_opens_the_browser(capsys):
    code, addresses, browser = run_serve(port=0)

    assert code == 0
    ((host, port),) = addresses
    (url,) = browser.call_args.args
    assert host == "127.0.0.1"
    assert url.startswith(f"http://127.0.0.1:{port}/?token=")
    assert f"wid is running at {url}" in capsys.readouterr().out


def test_a_taken_default_port_falls_back_to_a_free_one(monkeypatch):
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        monkeypatch.setattr(server, "DEFAULT_PORT", taken.getsockname()[1])

        code, addresses, browser = run_serve(open_browser=False)

        ((_, port),) = addresses
        assert code == 0
        assert port != taken.getsockname()[1]
        browser.assert_not_called()


def test_the_command_line_flags_start_the_server_instead_of_the_terminal():
    with (
        patch("wid.ui.app.RollerApp") as app,
        patch.object(server, "serve", return_value=0) as serve,
        pytest.raises(SystemExit) as stop,
    ):
        main(["--web", "--port", "9000", "--no-browser"])

    assert stop.value.code == 0
    serve.assert_called_once_with(port=9000, open_browser=False, open_path=None)
    app.assert_not_called()
    with pytest.raises(SystemExit) as refused:
        main(["--port", "9000"])
    assert refused.value.code == 2
    # A port outside 0-65535 is a usage error, not a traceback.
    with pytest.raises(SystemExit) as refused:
        main(["--web", "--port", "70000"])
    assert refused.value.code == 2
