"""``wid --web``: serve the game to a browser on this machine only."""

import os
import secrets
import socket
import sys
import webbrowser

import uvicorn

from wid.game import Game
from wid.settings import recovery_path
from wid.web.app import create_app

# The loopback address only, so nothing outside this machine can reach the game.
HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def listening_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Lets a quick restart reuse the port while the old one is still closing. Windows would let
    # another program share the port instead, so it is left out there.
    if os.name != "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, port))
        sock.listen()
    except OSError:
        sock.close()
        raise
    return sock


def open_socket(port: int | None) -> socket.socket:
    """Listen on ``port``, or on the default port and then any free one when it is taken."""
    if port is not None:
        return listening_socket(port)
    try:
        return listening_socket(DEFAULT_PORT)
    except OSError:
        return listening_socket(0)


def serve(
    *, port: int | None = None, open_browser: bool = True, open_path: str | None = None
) -> int:
    """Run until Ctrl+C and return the process exit code; ``open_path`` is a save to open."""
    try:
        sock = open_socket(port)
    except OSError as error:
        print(f"Could not listen on {HOST}: {error}", file=sys.stderr)
        return 1
    # A new token each launch: only the browser that opens this address can use the game.
    token = secrets.token_urlsafe(16)
    url = f"http://{HOST}:{sock.getsockname()[1]}/?token={token}"
    print(f"wid is running at {url} (press Ctrl+C to stop)", flush=True)
    # The socket already listens, so a browser that is quicker than the server just waits.
    if open_browser:
        webbrowser.open(url)
    game = Game(recovery_path=recovery_path())
    greeting = game.open_file(open_path) if open_path else ""
    app = create_app(game, token, greeting=greeting)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    with sock:
        try:
            server.run(sockets=[sock])
        except KeyboardInterrupt:
            pass
    print("wid stopped.")
    return 0
