"""Plain-text exports of a game's history. No Textual, so it is easy to test."""

from collections.abc import Sequence
from itertools import groupby

from wid.formatting import one_line
from wid.history import HistoryEntry
from wid.sessions import CharacterDetails


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
    name: str,
    character: CharacterDetails,
    entries: Sequence[HistoryEntry],
    *,
    sheet: Sequence[str] = (),
    notes: str = "",
    statistics: str = "",
) -> str:
    """The game as Markdown: title, character line, sheet, notes, the history, then statistics.

    The sheet's lines are a list, and the notes go in as written, since they are Markdown
    already. Each history entry's text goes in a code block so the dice lines keep their layout
    and anything typed by the player cannot be taken for Markdown.
    """
    title = one_line(name) or "Session history"
    lines = [f"# {title}", ""]
    details = [value for value in (character.name, character.looks, character.nature) if value]
    if details:
        lines += ["Character: " + ", ".join(one_line(value) for value in details), ""]
    if sheet:
        lines += ["## Sheet", "", *(f"- {line}" for line in sheet), ""]
    if notes.strip():
        lines += ["## Notes", "", notes.strip(), ""]
    for index, entry in enumerate(entries, start=1):
        text = str(entry)
        fence = fence_for(text)
        lines += [heading_for(index, entry), "", f"{fence}text", text, fence, ""]
    if statistics:
        lines += ["## Statistics", "", statistics, ""]
    return "\n".join(lines)
