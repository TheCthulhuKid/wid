"""Compatibility launcher for the packaged card dealer."""

from huckdeck.cli import main
from huckdeck.ui.app import HuckDeck

__all__ = ["HuckDeck", "main"]


if __name__ == "__main__":
    main()
