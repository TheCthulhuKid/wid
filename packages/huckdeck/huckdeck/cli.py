import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from huckdeck.ui.app import HuckDeck


def package_version() -> str:
    try:
        return version("huckdeck")
    except PackageNotFoundError:
        return "unknown"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="huckdeck", description="A terminal card dealer with suited jokers."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.parse_args(argv)
    HuckDeck().run()
