"""Print the CHANGELOG.md section for a release tag, as the notes for its GitHub release.

    python release/changelog_notes.py v0.4.2

A tag with no section, or an empty one, is an error, so a release cannot go out without notes.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def section(changelog: str, tag: str) -> str:
    """The text under ``## [<version>]``, up to the next section or the link list at the end."""
    version = re.escape(tag.removeprefix("v"))
    match = re.search(
        rf"^## \[{version}\][^\n]*\n(.*?)(?=^## |^\[[^\]]+\]: |\Z)", changelog, re.M | re.S
    )
    notes = match.group(1).strip() if match else ""
    if not notes:
        raise LookupError(f"CHANGELOG.md has no notes for {tag}.")
    return notes


def main(argv: list[str]) -> int:
    try:
        print(section(CHANGELOG.read_text(encoding="utf-8"), argv[0]))
    except LookupError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
