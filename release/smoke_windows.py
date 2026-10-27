"""Drive the built wid.exe through a real Windows pseudo console and press real keys.

    python release/smoke_windows.py path\\to\\wid.exe

Needs pywinpty (``uv sync --group smoke``). Unlike ``wid --self-test``, which runs the app
without a terminal, this goes through Textual's Windows console driver, as a user's keyboard
does. It runs with a private %APPDATA%, so the user's own settings are never touched.
Exit code 0 means every step passed.
"""

import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

# Escape sequences a terminal would interpret: colours, cursor moves, titles, mode switches.
ANSI = re.compile(
    r"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Z0-9]|\x1b[=>78]"
)

TAB, ENTER, ESCAPE, CTRL_R, CTRL_Q = "\t", "\r", "\x1b", "\x12", "\x11"


def visible_text(raw: str) -> str:
    """What a person would read on the screen: the output with control sequences removed."""
    return ANSI.sub("", raw)


class Terminal:
    """A child process in a pseudo console, with its output collected on a background thread."""

    def __init__(self, command: list[str], env: dict[str, str], rows: int = 40, cols: int = 100):
        from winpty import PtyProcess

        self.process = PtyProcess.spawn(command, dimensions=(rows, cols), env=env)
        self.raw = ""
        self.lock = threading.Lock()
        threading.Thread(target=self.collect, daemon=True).start()

    def collect(self) -> None:
        while True:
            try:
                chunk = self.process.read(65536)
            except (EOFError, OSError):
                return
            with self.lock:
                self.raw += chunk

    def mark(self) -> None:
        """Forget what has been drawn so far, so the next wait only sees new output."""
        with self.lock:
            self.raw = ""

    def text(self) -> str:
        with self.lock:
            return visible_text(self.raw)

    def send(self, keys: str) -> None:
        self.process.write(keys)

    def wait_for(self, expected: str, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if expected in self.text():
                return True
            time.sleep(0.1)
        return False

    def wait_for_exit(self, timeout: float = 15.0) -> int | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.process.isalive():
                return self.process.exitstatus
            time.sleep(0.1)
        return None


def run(exe: str) -> int:
    failures: list[str] = []

    def step(name: str, passed: bool, detail: str = "") -> None:
        print(
            f"{'ok  ' if passed else 'FAIL'} {name}"
            + (f" - {detail}" if detail and not passed else "")
        )
        if not passed:
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="wid-smoke-") as appdata:
        env = {key: value for key, value in os.environ.items() if key != "XDG_CONFIG_HOME"}
        env["APPDATA"] = appdata
        terminal = Terminal([exe], env)

        step("the start screen appears", terminal.wait_for("Start game"), terminal.text()[-300:])

        terminal.mark()
        terminal.send(TAB + TAB + ENTER)
        step("Tab, Tab, Enter starts the game", terminal.wait_for("Roll beside an attribute"))

        terminal.mark()
        terminal.send(CTRL_R)
        step("Ctrl+R rolls and shows the result", terminal.wait_for("Hits:"))

        terminal.mark()
        terminal.send("d")
        step("D opens the theme picker", terminal.wait_for("Search for themes"))
        terminal.send(ESCAPE)
        time.sleep(0.5)

        terminal.mark()
        terminal.send("s")
        step("S opens the Session tab", terminal.wait_for("Session name"))

        terminal.mark()
        terminal.send("c")
        step("C returns to the Character tab", terminal.wait_for("Looks"))

        # The roll is unsaved, so Ctrl+Q asks first; the Quit button has the focus.
        terminal.mark()
        terminal.send(CTRL_Q)
        step("Ctrl+Q asks before losing the roll", terminal.wait_for("Unsaved changes"))
        terminal.send(ENTER)
        status = terminal.wait_for_exit()
        step("Enter on Quit exits with code 0", status == 0, f"exit status {status}")

        settings = Path(appdata) / "wid" / "settings.json"
        saved = json.loads(settings.read_text(encoding="utf-8")) if settings.is_file() else {}
        step(
            "the last tab was saved under %APPDATA%\\wid",
            saved.get("tab") == "character",
            f"{settings} -> {saved}",
        )

    print("smoke test passed" if not failures else f"smoke test FAILED ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(run(sys.argv[1]))
