import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))

import smoke_windows  # noqa: E402


def test_control_sequences_are_removed_and_a_screen_painted_in_pieces_reads_as_one_line():
    raw = (
        "\x1b[?25l\x1b[38;2;1;120;212m ▊ \x1b[1m\x1b[0mStart\x1b[39m game"
        "\x1b]0;wid\x07\x1b[2J\x1b[H"
    )
    assert smoke_windows.visible_text(raw) == " ▊ Start game"
    raw = "\x1b[5;3HHits: \x1b[32m1\x1b[0m (dice 1)"
    assert smoke_windows.visible_text(raw) == "Hits: 1 (dice 1)"
