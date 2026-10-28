import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    try:
        return version("wid")
    except PackageNotFoundError:
        return "unknown"


def port_number(text: str) -> int:
    try:
        port = int(text)
    except ValueError:
        port = None
    if port is None or not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"{text!r} is not a port (use 0 to 65535)")
    return port


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wid", description="A dice roller for We're in Danger, in the terminal or a browser."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument("session", nargs="?", help="a saved game to open (a .json file)")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="check that this installation works, without a terminal, then exit",
    )
    parser.add_argument(
        "--gm",
        action="store_true",
        help="run the Game Master's screen: Dangers and the scene instead of a character",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="play in a web browser on this computer instead of the terminal",
    )
    parser.add_argument(
        "--port", type=port_number, help="with --web: the port (default 8765, or any free one)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="with --web: only print the address to open"
    )
    arguments = parser.parse_args(argv)
    if (arguments.port is not None or arguments.no_browser) and not arguments.web:
        parser.error("--port and --no-browser need --web")
    if arguments.self_test:
        from wid.selftest import run_self_test

        raise SystemExit(run_self_test())
    from wid.sessions import file_kind

    # A save opens in the mode it was saved in; --gm on a player's file is refused on screen.
    gm = arguments.gm or (arguments.session is not None and file_kind(arguments.session) == "gm")
    if arguments.web:
        from wid.web.server import serve

        raise SystemExit(
            serve(
                port=arguments.port,
                open_browser=not arguments.no_browser,
                open_path=arguments.session,
                gm=gm,
            )
        )
    # Imported here so --web and --self-test do not load the terminal interface first.
    from wid.settings import gm_recovery_path, recovery_path

    if gm:
        from wid.ui.gm_app import GmApp

        GmApp(recovery_path=gm_recovery_path(), open_path=arguments.session).run()
        return
    from wid.ui.app import RollerApp

    RollerApp(recovery_path=recovery_path(), open_path=arguments.session).run()
