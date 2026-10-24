"""Compatibility launcher; the application lives in wid.ui.app."""

from wid.cli import main
from wid.ui.app import RollerApp

__all__ = ["RollerApp", "main"]

if __name__ == "__main__":
    main()
