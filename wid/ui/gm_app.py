"""The GM's terminal screen: the scene on the left, the activations on the right."""

from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.tabbed_content import ContentTabs

from wid.dangers import BARRICADE_MAX, DANGERS_MAX, classes_for
from wid.formatting import (
    GM_KIT_QUESTION,
    NO_ACTIVATION_HINT,
    activation_line,
    barricade_text,
    danger_summary,
    loadout_rows,
    revelations_line,
    scene_summary,
)
from wid.gm import GmGame
from wid.profiles import Genre, WiDProfile
from wid.ui.base import BaseApp, ButtonTables, PaletteCommand
from wid.ui.dialogs import CANCEL, Answer
from wid.ui.sessions import SessionActions
from wid.ui.widgets import (
    ActivationGroup,
    DangerName,
    GameRow,
    NotesGroup,
    RemoveDangerButton,
    SceneGroup,
    SessionFile,
    SessionName,
)

KEEP_SCENE = "keep-scene"
START_NEW = "start-new"

# Buttons that run one game action and show what it says.
GAME_BUTTONS: dict[str, Callable[[GmGame], str]] = {
    "undo": GmGame.undo,
    "roll-d6": GmGame.roll_one_die,
    "activate": GmGame.activate,
    "clash": GmGame.clash,
    "barricade-up": lambda game: game.move_barricade(1),
    "barricade-down": lambda game: game.move_barricade(-1),
}


class GmApp(SessionActions, BaseApp):
    """The GM's terminal screen: the kit and the scene on the left, the activations on the
    right."""

    KIT_QUESTION = GM_KIT_QUESTION
    KIT_ANSWERS = (
        Answer(KEEP_SCENE, "Keep scene", "warning"),
        Answer(START_NEW, "Start new", "warning"),
        Answer(CANCEL, "Cancel"),
    )
    BINDINGS: ClassVar = [
        ("d", "change_theme", "Theme"),
        ("e", "show_tab('scene')", "Scene"),
        ("s", "show_tab('session')", "Session"),
        ("ctrl+r", "activate", "Activate"),
        ("ctrl+l", "toggle_history", "Log"),
    ]

    def make_game(self, rng: Random | None, recovery_path: Path | None) -> GmGame:
        return GmGame(rng=rng, recovery_path=recovery_path)

    @property
    def genre(self) -> Genre:
        return self.game.genre

    def compose_configuration(self) -> ComposeResult:
        yield GameRow(start=False, id="profile-fields")
        with TabbedContent(id="details"):
            with TabPane("Scene", id="tab-scene"):
                yield SceneGroup(id="scene")
            with TabPane("Session", id="tab-session"):
                yield SessionName()
                yield NotesGroup()
                yield SessionFile(new_character=False)

    def compose_output(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("Show log", id="toggle-history")
            yield Button("Activate Danger", id="activate", variant="primary")
            yield Button("Roll 1d6", id="roll-d6", tooltip="Roll one die outside an activation")
            yield Button("Undo", id="undo", disabled=True, tooltip="Take back the last change")
        yield Static(id="feedback", markup=False)
        yield ActivationGroup()

    def action_show_tab(self, name: str) -> None:
        tabs = self.query_one("#details", TabbedContent)
        tabs.active = f"tab-{name}"
        # Focus the tab bar, not a field: letters typed in a field would swallow the shortcuts.
        tabs.query_one(ContentTabs).focus()

    def action_activate(self) -> None:
        self.act(self.game.activate)

    def collect(self) -> None:
        game = self.game
        game.name = self.query_one("#session-name", Input).value
        game.path = self.query_one("#session-path", Input).value
        game.notes = self.query_one("#session-notes", TextArea).text

    def refresh_sheet(self) -> None:
        scene = self.game.scene
        # Undo can bring the kit back with the scene.
        if self.query_one("#genre", Select).value != self.genre:
            self.show_genre()
            self.show_classes()
        with self.prevent(Select.Changed, Checkbox.Changed, Input.Changed):
            self.query_one("#pc-count", Select).value = scene.pc_count
            self.query_one("#hostile", Checkbox).value = scene.hostile
            for index in range(DANGERS_MAX):
                self.query_one(f"#danger-row-{index}").display = index < len(scene.dangers)
                if index < len(scene.dangers):
                    danger = scene.dangers[index]
                    summary = danger_summary(danger, index, scene.pc_count)
                    self.query_one(f"#danger-summary-{index}", Static).update(summary)
                    self.query_one(f"#danger-name-{index}", Input).value = danger.name
        self.query_one("#scene-summary", Static).update(scene_summary(scene))
        self.query_one("#add-danger", Button).disabled = len(scene.dangers) >= DANGERS_MAX
        for button_id in ("commit-hits", "activate"):
            self.query_one(f"#{button_id}", Button).disabled = not scene.dangers
        self.query_one("#clash", Button).disabled = not (scene.dangers and scene.hostile)
        self.update_trackers()
        activation = self.game.last_activation
        self.query_one("#activation", Static).update(
            activation_line(activation) if activation else NO_ACTIVATION_HINT
        )
        table = self.query_one("#loadout", DataTable)
        table.clear()
        table.add_rows(loadout_rows(scene.loadout, self.genre))
        self.finish_refresh()

    def update_trackers(self) -> None:
        """Show the kit's trackers only: a Danger's standing, the barricade, the revelations."""
        profile, scene = self.profile, self.game.scene
        self.query_one("#standing-row").display = profile.has_standing
        self.query_one("#barricade-row").display = profile.has_barricade
        self.query_one("#barricade", Static).update(barricade_text(scene.barricade))
        self.query_one("#barricade-up", Button).disabled = scene.barricade >= BARRICADE_MAX
        self.query_one("#barricade-down", Button).disabled = scene.barricade == 0
        self.query_one("#revelations-field").display = profile.has_revelations
        self.query_one("#revelations", Static).update(revelations_line(scene))
        with self.prevent(Select.Changed):
            self.query_one("#revelation-count", Select).value = scene.revelations
        done = scene.revelation_progress >= scene.revelation_total
        for button_id in ("hits-spent", "task-done"):
            self.query_one(f"#{button_id}", Button).disabled = done

    @property
    def profile(self) -> WiDProfile:
        return self.game.profile

    def show_game(self) -> None:
        game = self.game
        with self.prevent(Input.Changed, Select.Changed):
            self.query_one("#session-name", Input).value = game.name
            self.query_one("#session-path", Input).value = game.path
            self.query_one("#genre", Select).value = game.genre
            self.show_classes()
        self.query_one("#session-notes", TextArea).load_text(game.notes)
        self.sub_title = game.name
        self.clear_log()
        self.refresh_sheet()

    def show_classes(self) -> None:
        """Offer the base classes and the kit's; the choice starts over at the first."""
        selector = self.query_one("#danger-class", Select)
        classes = classes_for(self.genre)
        selector.set_options([(kind.label, kind) for kind in classes])
        selector.value = classes[0]

    def change_kit(self, genre: Genre, answer: str) -> str | None:
        if answer == KEEP_SCENE:
            return self.game.keep_scene(genre)
        if answer == START_NEW:
            return self.game.start_new(genre)
        return None

    def add_danger(self) -> None:
        name_field = self.query_one("#new-danger-name", Input)
        name = name_field.value
        danger_class = self.query_one("#danger-class", Select).value
        difficulty = self.query_one("#difficulty", Select).value
        standing = self.query_one("#danger-standing", Select).value
        if not self.profile.has_standing:
            standing = None
        if self.act(lambda: self.game.add_danger(name, danger_class, difficulty, standing)):
            name_field.value = ""

    def remove_danger(self, index: int) -> None:
        self.act(lambda: self.game.remove_danger(index))

    def commit_hits(self) -> None:
        amount = self.query_one("#amount", Select).value
        self.act(lambda: self.game.commit_hits(amount))

    def raise_threshold(self) -> None:
        amount = self.query_one("#amount", Select).value
        self.act(lambda: self.game.raise_threshold(amount))

    def task_strain(self) -> None:
        complexity = self.query_one("#task", Select).value
        self.act(lambda: self.game.task_strain(complexity))

    def spend_hits(self) -> None:
        amount = self.query_one("#amount", Select).value
        self.act(lambda: self.game.spend_hits(amount))

    def task_done(self) -> None:
        complexity = self.query_one("#task", Select).value
        self.act(lambda: self.game.task_done(complexity))

    def select_changed(self, event: Select.Changed) -> None:
        value = event.value
        if event.select.id == "pc-count":
            self.act(lambda: self.game.set_pc_count(value))
        elif event.select.id == "revelation-count":
            self.act(lambda: self.game.set_revelations(value))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "hostile" and event.value == event.checkbox.value:
            hostile = event.value
            self.act(lambda: self.game.set_hostile(hostile))

    def on_input_changed(self, event: Input.Changed) -> None:
        field = event.input
        if isinstance(field, DangerName) and event.value == field.value:
            self.game.rename_danger(field.index, event.value)

    def button_tables(self) -> ButtonTables:
        return TYPED_BUTTONS, GAME_BUTTONS, APP_BUTTONS

    def palette_commands(self) -> Sequence[PaletteCommand]:
        return PALETTE_COMMANDS


# The tables below name GmApp's methods, so they follow the class.

TYPED_BUTTONS: dict[type[Button], Callable[[GmApp, Button], None]] = {
    RemoveDangerButton: lambda app, button: app.remove_danger(button.index),
}

PALETTE_COMMANDS: tuple[PaletteCommand, ...] = (
    ("Save session", "Save the game to the session file", GmApp.action_save_session),
    ("Load session", "Open a saved session", GmApp.action_load_session),
    (
        "Export history",
        "Write the scene, notes and history to a Markdown file",
        GmApp.action_export_history,
    ),
    ("Activate Danger", "Roll the Danger's ability, target and attribute", GmApp.action_activate),
    ("Undo", "Take back the last change to the scene", lambda app: app.act(app.game.undo)),
)

APP_BUTTONS: dict[str, Callable[[GmApp], None]] = {
    "save-session": GmApp.action_save_session,
    "export-history": GmApp.action_export_history,
    "load-session": GmApp.action_load_session,
    "toggle-history": GmApp.action_toggle_history,
    "add-danger": GmApp.add_danger,
    "commit-hits": GmApp.commit_hits,
    "raise-threshold": GmApp.raise_threshold,
    "task-strain": GmApp.task_strain,
    "hits-spent": GmApp.spend_hits,
    "task-done": GmApp.task_done,
}
