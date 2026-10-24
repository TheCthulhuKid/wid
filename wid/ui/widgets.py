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
from wid.rolls import BonusKind, PowerMode

BONUS_LABELS = {
    BonusKind.EXPERTISE: "Expertise",
    BonusKind.APPROPRIATE_ITEM: "Appropriate Item",
    BonusKind.INAPPROPRIATE_ITEM: "Inappropriate Item",
}
CHARACTER_LABELS = {"name": "Name", "looks": "Looks", "nature": "Nature"}


class ProfileGroup(Vertical):
    def compose(self) -> ComposeResult:
        with Horizontal(id="profile-fields"):
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
        with Grid(id="character-fields"):
            for field, label in CHARACTER_LABELS.items():
                with Vertical(classes="field"):
                    yield Label(label)
                    yield Input(placeholder=label, id=f"character-{field}")
        with Vertical(id="attribute-setup"):
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
                        yield Button(
                            "Roll", id=f"roll-attribute-{index}", variant="primary", disabled=True
                        )


class NotesGroup(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Session notes (Markdown)")
        yield TextArea(placeholder="Character and campaign notes", id="session-notes")
        with VerticalScroll(id="notes-preview-panel"):
            yield Markdown(open_links=False, id="notes-preview")
        with Horizontal(id="notes-toolbar"):
            yield Button("Preview", id="toggle-notes-preview")
            yield Button("Bold", id="notes-bold")
            yield Button("Italic", id="notes-italic")
            yield Button("Heading", id="notes-heading")

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


class SessionGroup(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Session name")
        yield Input(placeholder="Name this game", max_length=100, id="session-name")
        yield NotesGroup()
        yield Label("Save / load file path (JSON)")
        yield Input(placeholder="/path/to/session.json", id="session-path")
        with Horizontal(classes="button-row"):
            yield Button("Save session", id="save-session")


class OptionsGroup(Vertical):
    def compose(self) -> ComposeResult:
        with Horizontal(id="test-options"):
            with Vertical(id="fear-field", classes="field"):
                yield Label("Fear")
                yield Select([(str(n), n) for n in range(4)], value=0, allow_blank=False, id="fear")
            with Vertical(classes="field", id="assisted-field"):
                yield Label("Assisted")
                yield Checkbox(id="assisted", tooltip="Assisted: +1 die; hits on 4+")
            with Vertical(classes="field", id="expertise-field"):
                yield Label("Expertise")
                with Horizontal(id="expertise-controls"):
                    yield Checkbox(id="expertise", tooltip="Include expertise: +1 hit")
                    yield Input(placeholder="Describe expertise", id="name-expertise")
                    yield Button("+1 hit", id="apply-expertise", disabled=True)
        with Vertical(id="powers"):
            yield Label("Power (extra dice / strain)")
            yield Select(
                [
                    ("None", PowerMode.NONE),
                    ("Reliable (+1 / +1)", PowerMode.RELIABLE),
                    ("Erratic (+2 / +2)", PowerMode.ERRATIC),
                ],
                value=PowerMode.NONE,
                allow_blank=False,
                id="power",
            )
        yield Static(id="pool")
        with Vertical(id="tech-controls"):
            yield Static("Tech: not initialized", id="tech-strength")
            yield Static(id="tech-attributes")
            yield Button("Initialize / replace Tech", id="initialize-tech")
            yield Label("Pre-roll Tech target")
            yield Select([("No Tech", -1)], value=-1, allow_blank=False, id="tech-target")
        with Vertical(id="items"):
            with Horizontal(id="item-target-row"):
                yield Label("Post-roll die")
                yield Select([("Roll first", -1)], value=-1, allow_blank=False, id="item-target")
            for kind in (BonusKind.APPROPRIATE_ITEM, BonusKind.INAPPROPRIATE_ITEM):
                label = BONUS_LABELS[kind]
                with Horizontal(classes="named-bonus"):
                    with Vertical(classes="field"):
                        yield Label(label)
                        yield Input(placeholder=f"{label} name", id=f"name-{kind}")
                    yield Button(
                        "+1 value",
                        id=f"apply-{kind}",
                        disabled=True,
                    )


class StrainGroup(Vertical):
    def compose(self) -> ComposeResult:
        yield Label(id="strain-total")
        for row, ending in enumerate(("Wound", "Wound", "Defeat")):
            with Horizontal(classes="strain-row"):
                with Horizontal(classes="strain-checks"):
                    for column in range(4):
                        index = row * 4 + column
                        description = ending if column == 3 else f"strain {column + 1}"
                        yield Checkbox(
                            ending if column == 3 else "",
                            id=f"strain-box-{index}",
                            classes="strain-ending" if column == 3 else "strain-box",
                            tooltip=f"Row {row + 1}: {description}",
                        )
                yield Input(placeholder=f"{ending} name", id=f"strain-name-{row}")
        yield Button("Take 1 strain", id="take-strain")
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
                yield Checkbox(f"Reroll die {index + 1}", id=f"reroll-die-{index}")
            yield Button("Reroll selected", id="reroll_button", disabled=True)
