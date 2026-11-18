"""A scenario sheet in Markdown, the GM's file for sharing and printing, read and written.

A sheet holds one or more scenarios, each from a ``# Title`` line to the next. Its fields are
``**Pitch:** ...`` paragraphs and ``**Waypoints**`` lists; each ``### Name`` is a Danger, with an
italic line such as ``*Heavy Brute*``, its loadout table and its description. wid works out a
Danger's hits, threshold and loadout itself, so a loadout table that disagrees is refused.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from wid.dangers import DangerClass, Difficulty
from wid.formatting import (
    INCITEMENT_ROLLS,
    SCENARIO_LIST_LABELS,
    danger_kind,
    loadout_rows,
    one_line,
)
from wid.profiles import Genre
from wid.rolls import Standing
from wid.scenario import (
    ENTRIES,
    INCITEMENTS,
    SCENARIO_DANGERS_MAX,
    Scenario,
    ScenarioDanger,
    ScenarioList,
)
from wid.sessions import renamed

TEXT_LABELS = {"pitch": "Pitch", "cast": "Cast", "themes": "Themes"}
LISTS = {label.lower(): kind for kind, label in SCENARIO_LIST_LABELS.items()}
INCITEMENT = "incitement"

AUTHOR = re.compile(r"^\*By (.+)\*$")
TEXT_LABEL = re.compile(r"^\*\*([^*]+):\*\*\s*(.*)$")
LIST_LABEL = re.compile(r"^\*\*([^*:]+)\*\*$")
KIND = re.compile(r"^\*([^*]+)\*")
ITEM = re.compile(r"^- ?(.*)$")
RULE = re.compile(r"^-{3,}$")
DANGER = re.compile(r"^### (.+)$")
ROW = re.compile(r"^(\|.*)$")

# Where the next plain line goes: a text field's lines, a list's entries, the incitement
# table, or nowhere, in a section wid does not keep (Tasks).
type Target = list[str] | ScenarioList | str | None


class ChooseScenario(Exception):
    """A sheet holds several scenarios, so the front end asks which one to import."""

    def __init__(self, titles: tuple[str, ...]):
        super().__init__("Which scenario?")
        self.titles = titles


@dataclass
class DangerDraft:
    """A Danger as the sheet writes it, before it is checked."""

    name: str
    kind: str | None = None
    abilities: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ScenarioDraft:
    """A scenario as the sheet writes it, before it is checked."""

    title: str
    texts: dict[str, list[str]] = field(default_factory=dict)
    lists: dict[ScenarioList, list[str]] = field(default_factory=dict)
    incitement: list[str] = field(default_factory=list)
    dangers: list[DangerDraft] = field(default_factory=list)
    target: Target = None
    # A heading with no field under it, such as a file's own title, is no scenario.
    found: bool = False

    @property
    def danger(self) -> DangerDraft | None:
        """The Danger being read, once the first ``### Name`` is passed."""
        return self.dangers[-1] if self.dangers else None


def read_sheets(text: str) -> tuple[Scenario, ...]:
    """The scenarios in a sheet, in the file's order; text before the first title is skipped."""
    drafts: list[ScenarioDraft] = []
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("# "):
            drafts.append(ScenarioDraft(line[2:].strip()))
        elif drafts and not RULE.match(line):
            read_line(drafts[-1], line)
    return tuple(built(draft) for draft in drafts if draft.found)


def chosen_sheet(text: str, choice: int | None = None) -> Scenario:
    """The one scenario in a sheet, or the one at ``choice``; several with no choice raise
    ``ChooseScenario`` with their titles."""
    sheets = read_sheets(text)
    if not sheets:
        raise ValueError("This file has no scenario: each starts with a line such as # Title.")
    if choice is None and len(sheets) > 1:
        raise ChooseScenario(tuple(sheet.title for sheet in sheets))
    index = choice or 0
    if index not in range(len(sheets)):
        raise ValueError("No such scenario in this file.")
    return sheets[index]


def read_line(draft: ScenarioDraft, line: str) -> None:
    """Take one line into the scenario being read: the first reader whose pattern matches and
    that takes the line, or else the field being written."""
    for pattern, read in LINE_READERS:
        if (match := pattern.match(line)) and read(draft, match):
            return
    if isinstance(draft.target, ScenarioList):
        if item := ITEM.match(line):
            draft.lists[draft.target].append(item.group(1))
    elif isinstance(draft.target, list):
        draft.target.append(line)


def start_danger(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    draft.dangers.append(DangerDraft(match.group(1).strip()))
    draft.target, draft.found = draft.dangers[-1].description, True
    return True


def read_author(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    """``*By ...*`` above the Dangers; under one, an italic line is its text."""
    if draft.danger is not None:
        return False
    draft.texts["author"], draft.found = [match.group(1)], True
    return True


def read_text_label(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    """``**Notes:**`` is the Danger's under a Danger and the scenario's above them; another
    label starts a section wid skips."""
    label, danger = match.group(1).strip().lower(), draft.danger
    draft.target = None
    if label == "notes" and danger is not None:
        draft.target = danger.notes
    elif label == "notes" or (label in TEXT_LABELS and danger is None):
        draft.target = draft.texts.setdefault(label, [])
    if draft.target is not None:
        draft.target.append(match.group(2))
        draft.found = True
    return True


def read_list_label(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    label = match.group(1).strip().lower()
    draft.target = LISTS.get(label) or (INCITEMENT if label == INCITEMENT else None)
    if isinstance(draft.target, ScenarioList):
        draft.lists.setdefault(draft.target, [])
    draft.found = draft.found or draft.target is not None
    return True


def read_kind(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    """A Danger's first italic line, such as ``*Heavy Brute*``."""
    danger = draft.danger
    if danger is None or danger.kind is not None:
        return False
    danger.kind = match.group(1).strip()
    return True


def read_row(draft: ScenarioDraft, match: re.Match[str]) -> bool:
    """A table row: the incitement's entry, or a Danger's ability. Headers are skipped."""
    cells = [cell.strip() for cell in match.group(1).strip("|").split("|")]
    if cells[0].lower() == "d6" or not cells[0].strip("-: "):
        return True
    second = cells[1] if len(cells) > 1 else ""
    if draft.target == INCITEMENT:
        draft.incitement.append(second)
    elif draft.danger is not None:
        draft.danger.abilities.append(second)
    return True


LINE_READERS = (
    (DANGER, start_danger),
    (AUTHOR, read_author),
    (TEXT_LABEL, read_text_label),
    (LIST_LABEL, read_list_label),
    (KIND, read_kind),
    (ROW, read_row),
)


def built(draft: ScenarioDraft) -> Scenario:
    title = draft.title
    texts = {name: "\n".join(lines).strip() for name, lines in draft.texts.items()}
    lists = {
        kind.value: entries(draft.lists.get(kind, []), ENTRIES, f"{title}: {label}")
        for kind, label in SCENARIO_LIST_LABELS.items()
    }
    incitement = entries(draft.incitement, INCITEMENTS, f"{title}: Incitement")
    if len(draft.dangers) > SCENARIO_DANGERS_MAX:
        raise ValueError(f"{title}: a scenario holds up to {SCENARIO_DANGERS_MAX} Dangers.")
    dangers = tuple(
        built_danger(danger, index, f"{title}, {danger.name}")
        for index, danger in enumerate(draft.dangers)
    )
    return Scenario(
        title=title,
        **texts,
        **lists,
        incitement=incitement,
        dangers=dangers,
        next_id=len(dangers),
    )


def entries(items: list[str], count: int, where: str) -> tuple[str, ...]:
    """A list's entries, padded to ``count``; more are refused."""
    if len(items) > count:
        raise ValueError(f"{where} has more than {count} entries.")
    return tuple(item.strip() for item in items) + ("",) * (count - len(items))


def built_danger(draft: DangerDraft, danger_id: int, where: str) -> ScenarioDanger:
    if draft.kind is None:
        raise ValueError(f"{where}: no line such as *Heavy Brute* under its name.")
    main, _, standing = draft.kind.partition(",")
    difficulty, _, danger_class = main.strip().partition(" ")
    danger = ScenarioDanger(
        id=danger_id,
        name=draft.name,
        difficulty=known(Difficulty, difficulty, where, "difficulty"),
        danger_class=known(DangerClass, danger_class.strip(), where, "class"),
        standing=known(Standing, standing.strip(), where, "standing") if standing else None,
        description="\n".join(draft.description).strip(),
        notes="\n".join(draft.notes).strip(),
    )
    require_loadout(danger, draft.abilities, where)
    return danger


def known[E: StrEnum](kind: type[E], word: str, where: str, what: str) -> E:
    """The choice ``word`` names, in any case; a sheet's Competent is now Heavy."""
    try:
        return kind(renamed(word.lower()))
    except ValueError:
        raise ValueError(f'{where}: wid knows no {what} "{word}".') from None


def require_loadout(danger: ScenarioDanger, abilities: list[str], where: str) -> None:
    """Refuse a loadout table whose abilities are not wid's; a Danger with none is fine."""
    if not abilities:
        return
    expected = [ability.label for ability in danger.loadout]
    written = [ability.replace("*", "").strip().capitalize() for ability in abilities]
    if len(written) != len(expected):
        raise ValueError(f"{where}: its loadout table has {len(written)} rows, not 6.")
    for die, (wid, sheet) in enumerate(zip(expected, written, strict=True), start=1):
        if wid != sheet:
            kind = danger_kind(danger)
            raise ValueError(f"{where}: die {die} is {wid} for a {kind}, not {sheet}.")


def write_sheet(scenario: Scenario, genre: Genre) -> str:
    """One scenario as a sheet, with wid's hits, threshold and loadout for ``genre``; a field
    left empty is left out, and the lists and incitement are always written."""
    lines = [f"# {one_line(scenario.title) or 'Untitled'}", ""]
    if author := one_line(scenario.author):
        lines += [f"*By {author}*", ""]
    for name, label in TEXT_LABELS.items():
        if text := getattr(scenario, name).strip():
            lines += [f"**{label}:** {text}", ""]
    for kind, label in SCENARIO_LIST_LABELS.items():
        items = (f"- {one_line(entry)}".rstrip() for entry in getattr(scenario, kind))
        lines += [f"**{label}**", *items, ""]
    rows = zip(INCITEMENT_ROLLS, scenario.incitement, strict=True)
    lines += ["**Incitement**", "| d6 | |", "|----|---|"]
    lines += [f"| {roll} | {one_line(entry)} |" for roll, entry in rows]
    lines.append("")
    if notes := scenario.notes.strip():
        lines += [f"**Notes:** {notes}", ""]
    for index, danger in enumerate(scenario.dangers):
        lines += danger_lines(danger, index, genre)
    return "\n".join(lines).rstrip() + "\n"


def danger_lines(danger: ScenarioDanger, index: int, genre: Genre) -> list[str]:
    rule = danger.difficulty.rule
    threshold = f"PCs x {rule.multiplier}" + (f" + {rule.addend}" if rule.addend else "")
    lines = [
        f"### {one_line(danger.label(index))}",
        f"*{danger_kind(danger)}* · **Hits:** {danger.hits_to_pass} · **Threshold:** {threshold}",
        "",
        "| d6 | Ability | Target | Attribute |",
        "|----|---------|--------|-----------|",
        *(f"| {' | '.join(row)} |" for row in loadout_rows(danger.loadout, genre)),
        "",
    ]
    if description := danger.description.strip():
        lines += [description, ""]
    if notes := danger.notes.strip():
        lines += [f"**Notes:** {notes}", ""]
    return lines
