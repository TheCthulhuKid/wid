"""A built-in check that an installation works, for release builds and bug reports.

It runs the real application headless (no terminal needed), so the same check works from
source, from an installed package and from a frozen program on any system.
"""

import asyncio
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from random import Random

from textual.widgets import Markdown, TabbedContent, TextArea

from wid.settings import load_settings
from wid.ui.app import RollerApp

Check = Callable[[RollerApp, object, Path], Awaitable[None]]


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def check_screen(app: RollerApp, pilot, folder: Path) -> None:
    require(app.query_one("#genre"), "the genre selector is missing")
    require(app.query_one("#output").styles.width.is_fraction, "the stylesheet did not load")


async def check_roll(app: RollerApp, pilot, folder: Path) -> None:
    await pilot.click("#start-game")
    await pilot.pause()
    require(app.session.attributes is not None, "Start game did not set the attributes")
    await pilot.press("ctrl+r")
    result = app.session.current_result
    require(result is not None and len(result.dice) == 4, "the roll produced no result")
    require(len(app.history) == 1, "the roll was not recorded in the history")


async def check_shortcuts(app: RollerApp, pilot, folder: Path) -> None:
    tabs = app.query_one("#details", TabbedContent)
    await pilot.press("s")
    require(tabs.active == "tab-session", "the S shortcut did not open the Session tab")
    await pilot.press("c")
    require(tabs.active == "tab-character", "the C shortcut did not open the Character tab")


async def check_theme(app: RollerApp, pilot, folder: Path) -> None:
    app.theme = "nord"
    await pilot.pause()
    require(load_settings(folder / "settings.json").theme == "nord", "the theme was not saved")


async def check_notes_preview(app: RollerApp, pilot, folder: Path) -> None:
    app.query_one("#session-notes", TextArea).load_text("# Heading\n\n- item")
    app.query_one("#details", TabbedContent).active = "tab-session"
    await pilot.pause()
    await pilot.click("#toggle-notes-preview")
    await pilot.pause()
    require(app.query_one("#notes-preview", Markdown).query("MarkdownH1"), "no Markdown preview")


async def check_export(app: RollerApp, pilot, folder: Path) -> None:
    target = folder / "history.md"
    app.export_history_path(str(target))
    await pilot.pause()
    require(target.is_file(), "the history was not exported")
    require("## 1." in target.read_text(encoding="utf-8"), "the exported history is empty")


CHECKS: tuple[tuple[str, Check], ...] = (
    ("start screen and stylesheet", check_screen),
    ("start a game and roll", check_roll),
    ("keyboard shortcuts", check_shortcuts),
    ("theme saved to the settings file", check_theme),
    ("Markdown notes preview", check_notes_preview),
    ("history export", check_export),
)


async def run_checks(folder: Path) -> list[tuple[str, str | None]]:
    """Run every check in one headless app; each result is (name, error or None)."""
    results: list[tuple[str, str | None]] = []
    app = RollerApp(rng=Random(1), settings_path=folder / "settings.json")
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        for name, check in CHECKS:
            try:
                await check(app, pilot, folder)
            except Exception as error:
                results.append((name, f"{type(error).__name__}: {error}"))
            else:
                results.append((name, None))
    return results


def run_self_test() -> int:
    """Print one line per check and return the process exit code (0 = all passed)."""
    with tempfile.TemporaryDirectory(prefix="wid-selftest-") as folder:
        results = asyncio.run(run_checks(Path(folder)))
    for name, error in results:
        print(f"{'ok  ' if error is None else 'FAIL'} {name}" + (f" - {error}" if error else ""))
    failed = [name for name, error in results if error is not None]
    print("wid self-test passed" if not failed else f"wid self-test FAILED ({len(failed)})")
    return 1 if failed else 0
