import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from wid.ui.app import RollerApp


def package_version() -> str:
    try:
        return version("wid")
    except PackageNotFoundError:
        return "unknown"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wid", description="A terminal dice roller for We're in Danger."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="check that this installation works, without a terminal, then exit",
    )
    arguments = parser.parse_args(argv)
    if arguments.self_test:
        from wid.selftest import run_self_test

        raise SystemExit(run_self_test())
    RollerApp().run()
