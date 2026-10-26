import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOWTO = (ROOT / "HOWTO.md").read_text(encoding="utf-8")
SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "wid").rglob("*.py"))

# Names the how-to uses for things on the screen. If one is renamed in the program, this
# fails and the how-to has to be updated with it.
SCREEN_LABELS = [
    "Genre kit",
    "Start game",
    "Load game",
    "Character",
    "Session",
    "Scared",
    "Assisted",
    "Expertise",
    "Items",
    "Appropriate Item",
    "Inappropriate Item",
    "Apply to die",
    "+1 value",
    "+1 hit",
    "Undo",
    "Reliable power",
    "Erratic power",
    "Use",
    "Sacrifice",
    "New scenario",
    "Reroll selected",
    "Take 1 strain",
    "Take 1 wound",
    "Save session",
    "Export history",
    "New character",
    "Preview",
    "Roll",
]

KIT_NAMES = [
    "Core WiD",
    "Heckboy",
    "Second Contact",
    "Oldheart",
    "Ball Season",
    "This Isn't Happening",
]


@pytest.mark.parametrize("label", SCREEN_LABELS)
def test_every_label_the_how_to_uses_exists_in_the_program(label):
    assert label in SOURCE, f"{label!r} is in HOWTO.md but not in the program"
    assert label in HOWTO


@pytest.mark.parametrize("kit", KIT_NAMES)
def test_every_genre_kit_is_described(kit):
    from wid.profiles import PROFILES

    assert kit in {profile.name for profile in PROFILES.values()}
    assert f"**{kit}**" in HOWTO


def test_every_kits_attributes_are_listed():
    from wid.profiles import PROFILES

    for profile in PROFILES.values():
        row = next(line for line in HOWTO.splitlines() if f"**{profile.name}**" in line)
        for attribute in profile.attributes:
            assert attribute in row, (profile.name, attribute)


def test_every_shortcut_in_the_how_to_is_a_real_binding():
    from wid.ui.app import RollerApp

    keys = {binding[0] for binding in RollerApp.BINDINGS}
    documented = re.findall(
        r"^\| \*\*(?:Ctrl\+)?([A-Z])\*\*(?: / \*\*([A-Z])\*\*)? \|", HOWTO, re.M
    )
    letters = {letter.lower() for pair in documented for letter in pair if letter}

    assert letters <= keys | {"r", "l", "q"}
    assert {"ctrl+r", "ctrl+l"} <= keys


def test_the_how_to_is_about_using_the_program_not_the_rules():
    for rule_text in ("5 or 6", "fumble: a value", "equal to or lower than"):
        assert rule_text not in HOWTO
