"""Plain-text exports of a game's history. No Textual, so it is easy to test."""

from collections.abc import Sequence
from itertools import groupby

from wid.history import HistoryEntry
from wid.sessions import CharacterDetails

NO_HISTORY = "No actions recorded."


def fence_for(text: str) -> str:
    """A code fence longer than any run of backticks inside ``text``."""
    longest = max(
        (len(list(run)) for char, run in groupby(text) if char == "`"),
        default=0,
    )
    return "`" * max(3, longest + 1)


def heading_for(index: int, entry: HistoryEntry) -> str:
    first_line = entry.action.splitlines()[0] if entry.action else "Note"
    return f"## {index}. {first_line}"


def history_markdown(
    name: str, character: CharacterDetails, entries: Sequence[HistoryEntry]
) -> str:
    """The history as Markdown: a title, the character line, then one section per entry.

    Each entry's text goes in a code block so the dice lines keep their layout and anything
    typed by the player (names, notes) cannot be taken for Markdown.
    """
    title = " ".join(name.split()) or "Session history"
    lines = [f"# {title}", ""]
    details = [value for value in (character.name, character.looks, character.nature) if value]
    if details:
        lines += ["Character: " + ", ".join(" ".join(value.split()) for value in details), ""]
    if not entries:
        return "\n".join([*lines, NO_HISTORY, ""])
    for index, entry in enumerate(entries, start=1):
        text = str(entry)
        fence = fence_for(text)
        lines += [heading_for(index, entry), "", f"{fence}text", text, fence, ""]
    return "\n".join(lines)
