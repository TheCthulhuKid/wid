from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Markdown,
    Select,
    Static,
    TextArea,
)

from wid.profiles import PROFILES, Genre
from wid.rolls import BonusKind, PowerMode, StrainTracker

BONUS_LABELS = {
    BonusKind.EXPERTISE: "Expertise",
    BonusKind.APPROPRIATE_ITEM: "Appropriate Item",
    BonusKind.INAPPROPRIATE_ITEM: "Inappropriate Item",
}
CHARACTER_LABELS = {"name": "Name", "looks": "Looks", "nature": "Nature"}


class AttributeRollButton(Button):
    """Rolls the attribute at ``index`` in the current kit."""

    def __init__(self, index: int, **kwargs):
        super().__init__("Roll", id=f"roll-attribute-{index}", **kwargs)
        self.index = index


class BonusButton(Button):
    """Applies the named bonus ``kind`` to the current test."""

    def __init__(self, label: str, kind: BonusKind, **kwargs):
        super().__init__(label, id=f"apply-{kind}", **kwargs)
        self.kind = kind


# Heckboy characters always have one reliable and one erratic power, in this order.
POWERS = (PowerMode.RELIABLE, PowerMode.ERRATIC)
POWER_LABELS = {
    PowerMode.RELIABLE: "Reliable power (+1 die / +1 strain)",
    PowerMode.ERRATIC: "Erratic power (+2 dice / +2 strain)",
}


class PowerName(Input):
    """Text box naming the Heckboy power at ``index`` of ``POWERS``."""

    def __init__(self, index: int, **kwargs):
        mode = POWERS[index].value.capitalize()
        super().__init__(placeholder=f"{mode} power name", id=f"power-name-{index}", **kwargs)
        self.index = index


class PowerToggle(Checkbox):
    """Uses the power ``mode`` in the next roll; at most one is ticked."""

    def __init__(self, mode: PowerMode, **kwargs):
        super().__init__("Use", id=f"use-{mode}", **kwargs)
        self.mode = mode


class BonusName(Input):
    """Text box naming the bonus ``kind``."""

    def __init__(self, kind: BonusKind, **kwargs):
        super().__init__(id=f"name-{kind}", **kwargs)
        self.kind = kind


class TechName(Input):
    """Text box naming the Tech piece at ``index``."""

    def __init__(self, index: int, **kwargs):
        super().__init__(
            placeholder="Empty: name it when you use it", id=f"tech-name-{index}", **kwargs
        )
        self.index = index


class TechUseButton(Button):
    """Adds the Tech piece at ``index`` to the chosen die of the current test."""

    def __init__(self, index: int, **kwargs):
        super().__init__("Use", id=f"use-tech-{index}", variant="primary", **kwargs)
        self.index = index


class SacrificeButton(Button):
    """Drops the Tech piece at ``index`` to 0 strength."""

    def __init__(self, index: int, **kwargs):
        super().__init__(
            "Sacrifice",
            id=f"sacrifice-tech-{index}",
            tooltip="Drop this piece to 0 to stop an extermination",
            **kwargs,
        )
        self.index = index


# Muscle, which sets the number of Tech slots, is ranked 1 to 3.
TECH_SLOTS = 3

LOCKED_NOTE = "Locked: boxes before a marked wound stay marked until that wound is cleared."
NOT_READY_NOTE = "Mark all the strain before this wound first."


class StrainBox(Checkbox):
    """One of the twelve strain boxes."""

    def __init__(self, index: int, label: str = "", *, tooltip: str, **kwargs):
        super().__init__(label, id=f"strain-box-{index}", tooltip=tooltip, **kwargs)
        self.index = index
        self.description = tooltip

    def sync(self, tracker: StrainTracker) -> None:
        """Show the tracker's state; boxes that cannot change are disabled and say why."""
        self.value = tracker.boxes[self.index]
        note = None
        if self.index in tracker.locked_boxes:
            note = LOCKED_NOTE
        elif not self.value and not tracker.markable(self.index):
            note = NOT_READY_NOTE
        self.disabled = note is not None
        self.tooltip = note or self.description


class StrainName(Input):
    """Name of the wound or defeat on strain ``row``."""

    def __init__(self, row: int, **kwargs):
        super().__init__(id=f"strain-name-{row}", **kwargs)
        self.row = row


class RerollDie(Checkbox):
    """Selects die ``index`` for an Oldheart reroll."""

    def __init__(self, index: int, **kwargs):
        super().__init__(f"Reroll die {index + 1}", id=f"reroll-die-{index}", **kwargs)
        self.index = index


class GameRow(Horizontal):
    """Genre kit selector beside the Start and Load buttons."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="field"):
            yield Label("Genre kit")
            yield Select(
                [(profile.name, genre) for genre, profile in PROFILES.items()],
                value=Genre.CORE,
                allow_blank=False,
                id="genre",
            )
        with Horizontal(id="game-controls"):
            yield Button("Start game", id="start-game", variant="primary")
            yield Button("Load game", id="load-session")


class CharacterGroup(Grid):
    def compose(self) -> ComposeResult:
        for field, label in CHARACTER_LABELS.items():
            with Vertical(classes="field"):
                yield Label(label)
                yield Input(placeholder=label, id=f"character-{field}")


class AttributeSetup(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Assign unique ranks (1–3), then start", id="attribute-instructions")
        with Vertical(id="attribute-ranks"):
            for index in range(3):
                with Horizontal(classes="attribute-row", id=f"attribute-row-{index}"):
                    yield Label(id=f"attribute-label-{index}")
                    yield Select(
                        [(str(rank), rank) for rank in range(1, 4)],
                        value=index + 1,
                        allow_blank=False,
                        id=f"attribute-rank-{index}",
                    )
                    yield AttributeRollButton(index, variant="primary", disabled=True)


class NotesGroup(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Session notes (Markdown)")
        with Horizontal(id="notes-toolbar"):
            yield Button("Preview", id="toggle-notes-preview")
            yield Button("Bold", id="notes-bold")
            yield Button("Italic", id="notes-italic")
            yield Button("Heading", id="notes-heading")
        yield TextArea(placeholder="Character and campaign notes", id="session-notes")
        with VerticalScroll(id="notes-preview-panel"):
            yield Markdown(open_links=False, id="notes-preview")

    @on(Button.Pressed, "#toggle-notes-preview")
    async def toggle_preview(self, event: Button.Pressed) -> None:
        event.stop()
        editor = self.query_one(TextArea)
        preview = self.query_one("#notes-preview-panel")
        showing_preview = not preview.display
        if showing_preview:
            await self.query_one(Markdown).update(editor.text)
        editor.display = not showing_preview
        preview.display = showing_preview
        event.button.label = "Edit" if showing_preview else "Preview"
        for button in self.query("#notes-toolbar Button").exclude("#toggle-notes-preview"):
            button.disabled = showing_preview
        if not showing_preview:
            editor.focus()

    @on(TextArea.Changed, "#session-notes")
    async def refresh_preview(self) -> None:
        if self.query_one("#notes-preview-panel").display:
            await self.query_one(Markdown).update(self.query_one(TextArea).text)

    @on(Button.Pressed, "#notes-bold, #notes-italic, #notes-heading")
    def format_notes(self, event: Button.Pressed) -> None:
        event.stop()
        editor = self.query_one(TextArea)
        start, end = sorted(editor.selection)
        if event.button.id == "notes-heading":
            last_row = end[0] - 1 if end[0] > start[0] and end[1] == 0 else end[0]
            start = (start[0], 0)
            end = (last_row, len(editor.document.get_line(last_row)))
            text = editor.get_text_range(start, end)
            replacement = "\n".join(f"# {line}" for line in text.split("\n"))
        else:
            marker, placeholder = {
                "notes-bold": ("**", "bold text"),
                "notes-italic": ("*", "italic text"),
            }[event.button.id]
            replacement = f"{marker}{editor.selected_text or placeholder}{marker}"
        editor.replace(replacement, start, end, maintain_selection_offset=False)
        editor.focus()


class SessionName(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Session name")
        yield Input(placeholder="Name this game", max_length=100, id="session-name")


class SessionFile(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Save / load file path (JSON)")
        yield Input(placeholder="/path/to/session.json", id="session-path")
        with Horizontal(classes="button-row"):
            yield Button("Save session", id="save-session", variant="primary")
            yield Button("Export history", id="export-history")
            yield Button("New character", id="new-character")


class RollOptions(Horizontal):
    """Scared, assisted and expertise for the next test."""

    def compose(self) -> ComposeResult:
        with Vertical(id="fear-field", classes="field"):
            yield Label("Scared")
            yield Select([(str(n), n) for n in range(4)], value=0, allow_blank=False, id="fear")
        with Vertical(classes="field", id="assisted-field"):
            yield Label("Assisted")
            yield Checkbox(id="assisted", tooltip="Assisted: +1 die; hits on 4+")
        with Vertical(classes="field", id="expertise-field"):
            yield Label("Expertise")
            with Horizontal(id="expertise-controls"):
                yield Checkbox(id="expertise", tooltip="Include expertise: +1 hit")
                yield BonusName(BonusKind.EXPERTISE, placeholder="Describe expertise")
                yield BonusButton("+1 hit", BonusKind.EXPERTISE, variant="primary", disabled=True)


class KitControls(Vertical):
    """Kit-specific controls that change the dice pool, and the resulting pool size."""

    def compose(self) -> ComposeResult:
        with Vertical(id="powers"):
            for index, mode in enumerate(POWERS):
                with Horizontal(classes="named-bonus"):
                    with Vertical(classes="field"):
                        yield Label(POWER_LABELS[mode])
                        yield PowerName(index)
                    yield PowerToggle(mode)
        yield Static(id="pool")


class ItemsGroup(Vertical):
    """The target die, then the named items or, in a kit with Tech, the Tech slots."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="item-target-row"):
            yield Label("Apply to die")
            yield Select([("Roll first", -1)], value=-1, allow_blank=False, id="item-target")
            yield Button("Undo", id="undo-bonus", disabled=True)
        with Vertical(id="item-rows"):
            for kind in (BonusKind.APPROPRIATE_ITEM, BonusKind.INAPPROPRIATE_ITEM):
                label = BONUS_LABELS[kind]
                with Horizontal(classes="named-bonus"):
                    with Vertical(classes="field"):
                        yield Label(label)
                        yield BonusName(kind, placeholder=f"{label} name")
                    yield BonusButton("+1 value", kind, variant="primary", disabled=True)
        with Vertical(id="tech-controls"):
            for index in range(TECH_SLOTS):
                with Horizontal(classes="named-bonus", id=f"tech-row-{index}"):
                    with Vertical(classes="field"):
                        yield Label(id=f"tech-label-{index}")
                        yield TechName(index)
                    yield TechUseButton(index, disabled=True)
                    yield SacrificeButton(index)
            with Horizontal(id="tech-scenario-row"):
                yield Static(id="tech-attributes")
                yield Button("New scenario", id="new-scenario")


class StrainGroup(Vertical):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button("Take 1 strain", id="take-strain", variant="primary")
            yield Button("Take 1 wound", id="take-wound", variant="primary")
        for row, ending in enumerate(("Wound", "Wound", "Defeat")):
            with Horizontal(classes="strain-row"):
                with Horizontal(classes="strain-checks"):
                    for column in range(4):
                        index = row * 4 + column
                        description = ending if column == 3 else f"strain {column + 1}"
                        yield StrainBox(
                            index,
                            ending if column == 3 else "",
                            classes="strain-ending" if column == 3 else "strain-box",
                            tooltip=f"Row {row + 1}: {description}",
                        )
                yield StrainName(row, placeholder=f"{ending} name")
        yield Static(id="strain-status", markup=False)


class RollerGroup(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static(id="tested-attribute", markup=False)
        yield Static("Roll a test to see individual outcomes.", id="dice", markup=False)
        yield Static(id="summary")
        yield Static(id="resources")
        with Vertical(id="reroll-controls"):
            yield Label("Oldheart: select dice from the current test")
            for index in range(7):
                yield RerollDie(index)
            yield Button("Reroll selected", id="reroll_button", disabled=True)
