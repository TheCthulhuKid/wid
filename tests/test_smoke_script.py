import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))

import smoke_windows  # noqa: E402


def test_control_sequences_are_removed_and_the_words_stay():
    raw = (
        "\x1b[?25l\x1b[38;2;1;120;212m ▊ \x1b[1m\x1b[0mStart\x1b[39m game"
        "\x1b]0;wid\x07\x1b[2J\x1b[H"
    )

    assert smoke_windows.visible_text(raw) == " ▊ Start game"


def test_a_screen_painted_in_pieces_still_reads_as_one_line():
    raw = "\x1b[5;3HHits: \x1b[32m1\x1b[0m (dice 1)"

    assert smoke_windows.visible_text(raw) == "Hits: 1 (dice 1)"


def test_the_smoke_script_can_be_imported_without_a_windows_console():
    assert callable(smoke_windows.run)
    assert smoke_windows.TAB == "\t" and smoke_windows.CTRL_Q == "\x11"
