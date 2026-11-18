"""The GM's terminal screen: the scenario and the scene on the left, the activations on the
right."""

from collections.abc import Callable, Iterator, Sequence
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

from wid.dangers import BARRICADE_MAX, DANGERS_MAX, DangerClass, Difficulty, Standing, classes_for
from wid.formatting import (
    GM_KIT_QUESTION,
    NO_ACTIVATION_HINT,
    SCENARIO_CHOICE_QUESTION,
    activation_line,
    barricade_text,
    class_reference_rows,
    danger_summary,
    danger_title,
    difficulty_reference_rows,
    loadout_heading,
    loadout_rows,
    replace_question,
    revelations_line,
    scenario_danger_text,
    scene_summary,
)
from wid.gm import GmGame
from wid.profiles import Genre, WiDProfile
from wid.scenario import (
    DANGER_TEXTS,
    ENTRIES,
    INCITEMENTS,
    SCENARIO_DANGERS_MAX,
    SCENARIO_TEXTS,
    Scenario,
    ScenarioList,
    Slot,
    TypedSlot,
)
from wid.scenario_sheet import ChooseScenario
from wid.ui.base import BaseApp, ButtonTables, PaletteCommand
from wid.ui.dialogs import CANCEL, Answer, ConfirmSessionAction, Question
from wid.ui.sessions import SessionActions
from wid.ui.widgets import (
    STRONGEST,
    ActivationGroup,
    DangerName,
    GameRow,
    NotesGroup,
    RemoveDangerButton,
    RemoveScenarioDangerButton,
    ScenarioDangerSelect,
    ScenarioGroup,
    SceneGroup,
    SessionFile,
    SessionName,
)

KEEP_SCENE = "keep-scene"
START_NEW = "start-new"

# Buttons that run one game action and show what it says.
GAME_BUTTONS: dict[str, Callable[[GmGame], str]] = {
    "undo": GmGame.undo,
    "clear-scenario": GmGame.clear_scenario,
    "end-scene": GmGame.end_scene,
    "lose-scene": GmGame.lose_scene,
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
        ("a", "show_tab('scenario')", "Scenario"),
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
        with TabbedContent(id="details", initial="tab-scene"):
            with TabPane("Scenario", id="tab-scenario"):
                yield ScenarioGroup(id="scenario")
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
        game.type_scene_notes(self.query_one("#scene-notes", TextArea).text)
        game.type_into_scenario({slot: text_of(field) for slot, field in self.scenario_fields()})

    def scenario_fields(self) -> Iterator[tuple[TypedSlot, Input | TextArea]]:
        """Each box the GM types the scenario into, with its slot in ``Scenario.typed``."""
        for field in SCENARIO_TEXTS:
            yield (Slot.TEXT, field), self.query_one(f"#scenario-{field}")
        for kind in ScenarioList:
            for index in range(ENTRIES):
                yield (kind.value, index), self.query_one(f"#{kind.value}-{index}", Input)
        for row in range(INCITEMENTS):
            yield (Slot.INCITEMENT, row), self.query_one(f"#incitement-{row}", Input)
        for index, danger in enumerate(self.game.scenario.dangers):
            for field in DANGER_TEXTS:
                yield (
                    (Slot.DANGER, danger.id, field),
                    self.query_one(f"#scenario-danger-{field}-{index}"),
                )

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
            self.show_acting()
        self.query_one("#scene-summary", Static).update(scene_summary(scene))
        self.show_scenario()
        self.show_scene_start()
        self.query_one("#end-scene", Button).disabled = not scene.overcome
        self.query_one("#lose-scene", Button).disabled = not scene.dangers or scene.overcome
        notes = self.query_one("#scene-notes", TextArea)
        if notes.text != scene.notes:
            notes.load_text(scene.notes)
        self.query_one("#add-danger", Button).disabled = len(scene.dangers) >= DANGERS_MAX
        for button_id in ("commit-hits", "raise-threshold", "activate"):
            self.query_one(f"#{button_id}", Button).disabled = not scene.dangers
        self.query_one("#clash", Button).disabled = not (scene.dangers and scene.hostile)
        self.update_trackers()
        activation = self.game.last_activation
        self.query_one("#activation", Static).update(
            activation_line(activation) if activation else NO_ACTIVATION_HINT
        )
        self.query_one("#loadout-heading", Static).update(loadout_heading(scene))
        table = self.query_one("#loadout", DataTable)
        table.clear()
        table.add_rows(loadout_rows(scene.loadout, self.genre))
        danger_text = scenario_danger_text(self.game.scene_from_scenario)
        self.query_one("#scene-danger-text", Static).update(danger_text)
        self.show_reference()
        self.finish_refresh()

    def show_acting(self) -> None:
        """Offer the strongest or one of the Dangers, once there is more than one to choose."""
        scene = self.game.scene
        self.query_one("#acting-row").display = len(scene.dangers) > 1
        selector = self.query_one("#acting", Select)
        titles = [
            (danger_title(danger, index), index) for index, danger in enumerate(scene.dangers)
        ]
        selector.set_options([("Strongest", STRONGEST), *titles])
        selector.value = STRONGEST if scene.acting is None else scene.acting_index

    def show_scene_start(self) -> None:
        """Offer the scenario's Dangers to start a scene with, once the last scene has ended."""
        dangers = self.game.scenario.dangers
        self.query_one("#start-scene-row").display = bool(dangers)
        selector = self.query_one("#scenario-scene", Select)
        if dangers:
            chosen = selector.value
            with self.prevent(Select.Changed):
                selector.set_options(
                    [(danger_title(danger, index), index) for index, danger in enumerate(dangers)]
                )
                selector.value = chosen if chosen in range(len(dangers)) else 0
        start = self.query_one("#start-scene", Button)
        start.disabled = bool(self.game.scene.dangers) or selector.is_blank()

    def show_scenario(self) -> None:
        scenario, profile = self.game.scenario, self.profile
        typed = scenario.typed()
        with self.prevent(Select.Changed, Input.Changed, TextArea.Changed):
            for slot, field in self.scenario_fields():
                if text_of(field) != typed[slot]:
                    set_text(field, typed[slot])
            for index in range(SCENARIO_DANGERS_MAX):
                shown = index < len(scenario.dangers)
                self.query_one(f"#scenario-danger-row-{index}").display = shown
                if not shown:
                    continue
                danger = scenario.dangers[index]
                summary = danger_summary(danger, index, self.game.scene.pc_count)
                self.query_one(f"#scenario-danger-summary-{index}", Static).update(summary)
                for part, value in (
                    ("class", danger.danger_class),
                    ("difficulty", danger.difficulty),
                    ("standing", danger.standing),
                ):
                    if value is not None:
                        self.query_one(f"#scenario-danger-{part}-{index}", Select).value = value
        for field in self.query("#scenario .standing-field"):
            field.display = profile.has_standing
        full = len(scenario.dangers) >= SCENARIO_DANGERS_MAX
        self.query_one("#add-scenario-danger", Button).disabled = full
        self.query_one("#clear-scenario", Button).disabled = scenario == Scenario()

    def show_reference(self) -> None:
        """The kit's classes, and the difficulties for the scene's PCs."""
        for table_id, rows in (
            ("#class-reference", class_reference_rows(self.genre)),
            ("#difficulty-reference", difficulty_reference_rows(self.game.scene.pc_count)),
        ):
            table = self.query_one(table_id, DataTable)
            table.clear()
            table.add_rows(rows)

    def update_trackers(self) -> None:
        """Show the kit's trackers only: a Danger's standing, the barricade, the revelations."""
        profile, scene = self.profile, self.game.scene
        self.query_one("#standing-row").display = profile.has_standing
        self.query_one("#mismatched-row").display = profile.has_standing
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
        """Offer the base classes and the kit's; a new Danger's choice starts over at the first."""
        classes = classes_for(self.genre)
        options = [(kind.label, kind) for kind in classes]
        with self.prevent(Select.Changed):
            for selector in self.query("#danger-class, #new-scenario-danger-class").results(Select):
                selector.set_options(options)
                selector.value = classes[0]
            for selector in self.query(ScenarioDangerSelect):
                if selector.id.startswith("scenario-danger-class-"):
                    selector.set_options(options)

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

    def add_scenario_danger(self) -> None:
        name_field = self.query_one("#new-scenario-danger-name", Input)
        name = name_field.value
        kind = self.scenario_danger_kind("new-scenario-danger")
        if self.act(lambda: self.game.add_scenario_danger(name, *kind)):
            name_field.value = ""

    def scenario_danger_kind(
        self, prefix: str, suffix: str = ""
    ) -> tuple[DangerClass, Difficulty, Standing | None]:
        """The class, difficulty and standing chosen in the selects ``prefix-part-suffix``."""
        danger_class, difficulty, standing = (
            self.query_one(f"#{prefix}-{part}{suffix}", Select).value
            for part in ("class", "difficulty", "standing")
        )
        return danger_class, difficulty, standing if self.profile.has_standing else None

    def import_scenario(self, choice: int | None = None) -> None:
        """Import from the Scenario file; a file of several asks which first."""
        path = self.query_one("#scenario-path", Input).value
        try:
            self.act(lambda: self.game.import_scenario_file(path, choice))
        except ChooseScenario as asked:
            answers = [
                Answer(f"scenario-{index}", title) for index, title in enumerate(asked.titles)
            ]
            self.push_screen(
                Question(SCENARIO_CHOICE_QUESTION, [*answers, Answer(CANCEL, "Cancel")]),
                self.finish_import,
            )

    def finish_import(self, answer: str) -> None:
        if answer == CANCEL:
            self.feedback("Import cancelled; the scenario is unchanged.")
            return
        self.import_scenario(int(answer.removeprefix("scenario-")))

    def export_scenario(self, overwrite: bool = False) -> None:
        path = self.query_one("#scenario-path", Input).value
        try:
            self.act(lambda: self.game.export_scenario(path, overwrite=overwrite))
        except FileExistsError as error:
            self.push_screen(
                ConfirmSessionAction(replace_question("file", error.filename)),
                self.finish_export_scenario,
            )

    def finish_export_scenario(self, confirmed: bool) -> None:
        if confirmed:
            self.export_scenario(overwrite=True)
        else:
            self.feedback("Export cancelled; existing file unchanged.")

    def start_scene(self) -> None:
        index = self.query_one("#scenario-scene", Select).value
        self.act(lambda: self.game.start_scene(index))

    def roll_on(self) -> None:
        kind = self.query_one("#roll-on-list", Select).value
        self.act(lambda: self.game.roll_on(kind))

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
        mismatched = self.query_one("#mismatched", Select).value if self.profile.has_standing else 0
        self.act(lambda: self.game.task_strain(complexity, mismatched))

    def spend_hits(self) -> None:
        amount = self.query_one("#amount", Select).value
        self.act(lambda: self.game.spend_hits(amount))

    def task_done(self) -> None:
        complexity = self.query_one("#task", Select).value
        self.act(lambda: self.game.task_done(complexity))

    def select_changed(self, event: Select.Changed) -> None:  # maybe shorten this later
        value = event.value
        if event.select.id == "pc-count":
            self.act(lambda: self.game.set_pc_count(value))
        elif event.select.id == "revelation-count":
            self.act(lambda: self.game.set_revelations(value))
        elif event.select.id == "scenario-scene":
            self.show_scene_start()
        elif event.select.id == "acting":
            self.act(lambda: self.game.choose_acting(None if value == STRONGEST else value))
        elif isinstance(event.select, ScenarioDangerSelect):
            index = event.select.index
            kind = self.scenario_danger_kind("scenario-danger", f"-{index}")
            self.act(lambda: self.game.change_scenario_danger(index, *kind))

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
    RemoveScenarioDangerButton: lambda app, button: app.act(
        lambda: app.game.remove_scenario_danger(button.index)
    ),
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
    "add-scenario-danger": GmApp.add_scenario_danger,
    "start-scene": GmApp.start_scene,
    "import-scenario": GmApp.import_scenario,
    "export-scenario": GmApp.export_scenario,
    "roll-on": GmApp.roll_on,
    "commit-hits": GmApp.commit_hits,
    "raise-threshold": GmApp.raise_threshold,
    "task-strain": GmApp.task_strain,
    "hits-spent": GmApp.spend_hits,
    "task-done": GmApp.task_done,
}


def text_of(field: Input | TextArea) -> str:
    return field.text if isinstance(field, TextArea) else field.value


def set_text(field: Input | TextArea, text: str) -> None:
    if isinstance(field, TextArea):
        field.load_text(text)
    else:
        field.value = text
