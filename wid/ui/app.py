from pathlib import Path
from random import Random
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Resize
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from wid.formatting import attribute_label, resources_line
from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import BonusKind, PowerMode, RollRequest, RollResult, RollSession
from wid.settings import load_settings, save_settings
from wid.ui.dialogs import ConfirmReset
from wid.ui.outcomes import dice_content, summary_content
from wid.ui.sessions import SessionActions
from wid.ui.widgets import (
    BONUS_LABELS,
    AttributeRollButton,
    AttributeSetup,
    BonusButton,
    BonusName,
    CharacterGroup,
    GameRow,
    ItemsGroup,
    KitControls,
    NotesGroup,
    RerollDie,
    RollerGroup,
    RollOptions,
    SessionFile,
    SessionName,
    StrainBox,
    StrainGroup,
    StrainName,
)


class RollerApp(SessionActions, App):
    """Configure tests in widgets; resolve them through the session model."""

    CSS_PATH = "roller.tcss"
    TITLE = "We're in Danger"
    BINDINGS: ClassVar = [
        ("d", "change_theme", "Theme"),
        ("ctrl+r", "roll", "Repeat attribute"),
        ("ctrl+l", "toggle_history", "Log"),
    ]

    def __init__(self, *, rng: Random | None = None, settings_path: Path | None = None):
        super().__init__()
        self.rng = rng if rng is not None else Random()
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self.session = RollSession()
        self.history: list[HistoryEntry] = []
        self.pending_genre: Genre | None = None
        self.tested_attribute = PROFILES[Genre.CORE].attributes[0]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with VerticalScroll(id="configuration"):
                yield GameRow(id="profile-fields")
                yield AttributeSetup(id="attribute-setup")
                yield RollOptions(id="test-options")
                yield KitControls()
                yield ItemsGroup(id="items")
                yield StrainGroup()
                with TabbedContent(id="details"):
                    with TabPane("Character", id="tab-character"):
                        yield CharacterGroup(id="character-fields")
                        yield NotesGroup()
                    with TabPane("Session", id="tab-session"):
                        yield SessionName()
                        yield SessionFile()
            with Vertical(id="output"):
                with Horizontal(id="actions"):
                    yield Button("Show log", id="toggle-history")
                yield Static(id="feedback", markup=False)
                yield RollerGroup()
        with Vertical(id="history-panel"):
            yield Label("Action history")
            yield RichLog(id="log", wrap=True, markup=False)
        yield Footer()

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width < 112, "compact")

    def action_toggle_history(self) -> None:
        panel = self.query_one("#history-panel")
        toggle = self.query_one("#toggle-history", Button)
        if panel.display and self.query_one("#log").has_focus:
            toggle.focus()
        panel.display = not panel.display
        toggle.label = "Hide log" if panel.display else "Show log"

    def on_mount(self) -> None:
        self.restore_theme()
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()

    def restore_theme(self) -> None:
        if self.settings.theme in self.available_themes:
            self.theme = self.settings.theme
        self.watch(self, "theme", self.remember_theme, init=False)
        self.watch(self, "theme", self.redraw_outcomes, init=False)

    def redraw_outcomes(self) -> None:
        result = self.session.current_result
        if result is None:
            return
        variables = self.get_css_variables()
        self.query_one("#dice", Static).update(dice_content(result, variables))
        self.query_one("#summary", Static).update(summary_content(result, variables))

    def remember_theme(self, theme: str) -> None:
        self.settings = self.settings.model_copy(update={"theme": theme})
        try:
            save_settings(self.settings, self.settings_path)
        except OSError as error:
            self.feedback(f"Could not save settings: {error}")

    def update_strain_controls(self) -> None:
        tracker = self.session.strain
        with self.prevent(Checkbox.Changed, Input.Changed):
            for box in self.query(StrainBox):
                box.sync(tracker)
            for field in self.query(StrainName):
                field.value = tracker.names[field.row]
        self.update_strain_status()

    def change_strain_box(self, index: int, marked: bool) -> None:
        try:
            self.session.strain = self.session.strain.set_box(index, marked)
        except ValueError as error:
            self.feedback(str(error))
        self.update_strain_controls()

    def update_strain_status(self) -> None:
        tracker = self.session.strain
        self.query_one("#strain-total", Label).update(
            f"Character strain: {sum(tracker.boxes)} / 12 marked"
        )
        status = "Mark strain as it is taken. A wound needs the strain before it marked first."
        if tracker.defeated:
            status = "Defeat — character ended."
            if tracker.names[2]:
                status += f" {tracker.names[2]}"
        self.query_one("#strain-status", Static).update(status)

    def update_attribute_controls(self) -> None:
        attributes = PROFILES[self.session.profile_id].attributes
        ready = self.session.attributes is not None
        self.query_one("#attribute-instructions", Label).update(
            "Roll beside an attribute to test it."
            if ready
            else "Assign unique ranks (1–3), then start"
        )
        self.query_one("#start-game", Button).display = not ready
        self.query_one("#initialize-tech", Button).disabled = not ready
        for index in range(3):
            label = self.query_one(f"#attribute-label-{index}", Label)
            selector = self.query_one(f"#attribute-rank-{index}", Select)
            button = self.query_one(f"#roll-attribute-{index}", Button)
            self.query_one(f"#attribute-row-{index}").display = index < len(attributes)
            selector.disabled = ready
            button.disabled = not ready
            if index < len(attributes):
                label.update(attributes[index])
                button.tooltip = f"Roll {attributes[index]}"
                if ready:
                    selector.value = self.session.attribute_rank(attributes[index])
        if ready and self.session.profile_id == Genre.SECOND_CONTACT:
            self.query_one("#tech-attributes", Static).update(
                f"Science {self.session.attribute_rank('Science')} + "
                f"Culture {self.session.attribute_rank('Culture')}"
            )
        else:
            self.query_one("#tech-attributes", Static).update("Set attributes first.")

    def start_game(self) -> None:
        try:
            self.session.configure_attributes(
                tuple(
                    self.query_one(f"#attribute-rank-{index}", Select).value
                    for index in range(len(PROFILES[self.session.profile_id].attributes))
                )
            )
        except ValueError as error:
            self.feedback(str(error))
            return
        self.update_attribute_controls()
        self.feedback("Attributes set for this game; press Roll beside an attribute.")

    def update_kit_controls(self) -> None:
        profile = PROFILES[self.session.profile_id]
        self.query_one("#powers").display = profile.has_powers
        self.query_one("#tech-controls").display = profile.has_tech
        self.update_tech_controls()
        self.update_reroll_controls()
        self.update_bonus_controls()

    def update_bonus_controls(self) -> None:
        result = self.session.current_result
        selector = self.query_one("#item-target", Select)
        previous = selector.value
        size = len(result.dice) if result is not None else 0
        options = [(f"Die {index + 1}", index) for index in range(size)]
        with self.prevent(Select.Changed):
            selector.set_options(options or [("Roll first", -1)])
            selector.value = (
                previous if type(previous) is int and 0 <= previous < size else (0 if size else -1)
            )
        selector.disabled = result is None
        for kind in BonusKind:
            available = result is not None and bool(getattr(self.session.bonuses, kind).strip())
            if kind == BonusKind.EXPERTISE and result is not None:
                available = available and not result.request.expertise
            self.query_one(f"#apply-{kind}", Button).disabled = not available

    def selected_dice(self) -> set[int]:
        return {box.index for box in self.query(RerollDie) if box.value}

    def update_reroll_controls(self) -> None:
        enabled = PROFILES[self.session.profile_id].has_rerolls
        self.query_one("#reroll-controls").display = enabled
        result = self.session.current_result
        for checkbox in self.query(RerollDie):
            available = enabled and result is not None and checkbox.index < len(result.dice)
            checkbox.display = available
            checkbox.disabled = not available
            if not available:
                checkbox.value = False
        self.query_one("#reroll_button", Button).disabled = (
            not enabled or result is None or not self.selected_dice()
        )

    def update_tech_controls(self) -> None:
        tech = self.session.tech
        strength = tech.remaining_bonus if tech is not None else 0
        self.query_one("#tech-strength", Static).update(
            f"Tech strength: {strength}" if tech is not None else "Tech: not initialized"
        )
        selector = self.query_one("#tech-target", Select)
        selector.disabled = strength == 0
        if strength == 0:
            selector.value = -1

    def has_resources(self) -> bool:
        return bool(
            self.session.total_strain
            or self.session.total_corruption
            or (self.session.tech is not None and self.session.tech.remaining_bonus)
            or any(self.session.strain.boxes)
            or any(self.session.strain.names)
        )

    def request_genre(self, genre: Genre) -> None:
        if genre == self.session.profile_id or self.pending_genre is not None:
            return
        self.pending_genre = genre
        if self.has_resources():
            self.push_screen(ConfirmReset(), self.finish_genre_change)
        else:
            self.finish_genre_change(True)

    def finish_genre_change(self, confirmed: bool) -> None:
        genre = self.pending_genre
        self.pending_genre = None
        if not confirmed or genre is None:
            self.query_one("#genre", Select).value = self.session.profile_id
            return
        self.session = RollSession(profile_id=genre, bonuses=self.session.bonuses)
        self.query_one("#power", Select).value = PowerMode.NONE
        self.query_one("#tech-target", Select).value = -1
        self.tested_attribute = PROFILES[genre].attributes[0]
        for index in range(3):
            self.query_one(f"#attribute-rank-{index}", Select).value = index + 1
        self.clear_result_display()
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()
        message = f"Switched to {PROFILES[genre].name}; active test cleared."
        self.feedback(message)
        self.record(HistoryEntry(notice=message))

    def clear_result_display(self) -> None:
        self.query_one("#tested-attribute", Static).update("")
        self.query_one("#dice", Static).update("Roll a test to see individual outcomes.")
        self.query_one("#summary", Static).update("")
        self.query_one("#resources", Static).update("")

    def feedback(self, message: str) -> None:
        self.query_one("#feedback", Static).update(message)

    def draft_request(self, *, preview: bool = False) -> RollRequest:
        return RollRequest(
            profile_id=self.session.profile_id,
            attribute=self.tested_attribute,
            attribute_rank=(
                self.session.attribute_rank(self.tested_attribute) if not preview else 1
            ),
            assisted=self.query_one("#assisted", Checkbox).value,
            fear_level=self.query_one("#fear", Select).value,
            expertise=self.query_one("#expertise", Checkbox).value,
            power=(
                self.query_one("#power", Select).value
                if PROFILES[self.session.profile_id].has_powers
                else PowerMode.NONE
            ),
            tech_target=(
                self.query_one("#tech-target", Select).value
                if not preview
                and PROFILES[self.session.profile_id].has_tech
                and self.query_one("#tech-target", Select).value != -1
                else None
            ),
        )

    def update_preview(self) -> None:
        request = self.draft_request(preview=True)
        size = request.pool_size()
        tech_selector = self.query_one("#tech-target", Select)
        old_target = tech_selector.value
        tech_selector.set_options([("No Tech", -1)] + [(f"Die {n + 1}", n) for n in range(size)])
        tech_selector.value = old_target if old_target != Select.BLANK and old_target < size else -1
        self.query_one("#pool", Static).update(f"Pool: {size}d6 — hits on {request.hit_threshold}+")
        if old_target != Select.BLANK and old_target >= size:
            self.feedback("Pool changed: cleared the out-of-range Tech target.")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != event.select.value:
            return
        if event.select.id == "genre" and event.value != Select.BLANK:
            self.request_genre(Genre(event.value))
        elif event.select.id in ("fear", "power"):
            self.update_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.value != event.checkbox.value:
            return
        if isinstance(event.checkbox, StrainBox):
            self.change_strain_box(event.checkbox.index, event.value)
        elif event.checkbox.id == "assisted":
            self.update_preview()
        elif isinstance(event.checkbox, RerollDie):
            self.update_reroll_controls()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.value != event.input.value:
            return
        if isinstance(event.input, StrainName):
            self.session.strain = self.session.strain.set_name(event.input.row, event.value)
            self.update_strain_status()
        elif isinstance(event.input, BonusName):
            self.session.set_bonus_name(event.input.kind, event.value)
            self.update_bonus_controls()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, AttributeRollButton):
            self.action_roll_attribute(event.button.index)
            return
        if isinstance(event.button, BonusButton):
            self.apply_bonus(event.button.kind)
            return
        action = {
            "save-session": self.action_save_session,
            "load-session": self.action_load_session,
            "take-strain": self.take_strain,
            "toggle-history": self.action_toggle_history,
            "start-game": self.start_game,
            "reroll_button": self.action_reroll,
            "initialize-tech": self.initialize_tech,
        }.get(event.button.id)
        if action is not None:
            action()

    def initialize_tech(self) -> None:
        try:
            tech = self.session.initialize_tech()
        except ValueError as error:
            self.feedback(str(error))
            return
        self.update_tech_controls()
        message = (
            f"Tech explicitly initialized/replaced: Science {tech.science} + "
            f"Culture {tech.culture} = {tech.remaining_bonus}."
        )
        self.feedback(message)
        self.record(HistoryEntry(notice=message))

    def take_strain(self) -> None:
        self.session.strain = self.session.strain.take(1)
        self.update_strain_controls()

    def apply_bonus(self, kind: BonusKind) -> None:
        if self.pending_genre is not None:
            return
        name = getattr(self.session.bonuses, kind)
        try:
            if kind == BonusKind.EXPERTISE:
                result = self.session.apply_expertise()
                action = f"Expertise {name}: +1 hit"
            else:
                index = self.query_one("#item-target", Select).value
                result = self.session.apply_item(kind, index)
                action = f"{BONUS_LABELS[kind]} {name}: +1 to die {index + 1}"
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.show_result(result)
        self.log_result(result, action, resource_cost=False)

    def show_result(self, result: RollResult) -> None:
        tech = self.session.tech
        self.query_one("#dice", Static).update(dice_content(result, self.get_css_variables()))
        self.query_one("#summary", Static).update(summary_content(result, self.get_css_variables()))
        self.query_one("#tested-attribute", Static).update(attribute_label(result))
        self.query_one("#resources", Static).update(
            resources_line(
                result,
                total_strain=self.session.total_strain,
                total_corruption=self.session.total_corruption,
                tech_remaining=tech.remaining_bonus if tech else None,
            )
        )
        for box in self.query(RerollDie):
            box.value = False
        self.update_reroll_controls()
        self.update_bonus_controls()

    def record(self, entry: HistoryEntry) -> None:
        self.history.append(entry)
        self.query_one("#log", RichLog).write(str(entry))

    def log_result(
        self, result: RollResult, action: str = "Roll", *, resource_cost: bool = True
    ) -> None:
        tech = self.session.tech
        self.record(
            HistoryEntry(
                action=action,
                result=result,
                charged=resource_cost,
                total_strain=self.session.total_strain,
                total_corruption=self.session.total_corruption,
                tech_remaining=tech.remaining_bonus if tech else None,
                expertise_name=self.session.bonuses.expertise,
            )
        )

    def action_roll_attribute(self, index: int) -> None:
        if self.pending_genre is not None or self.session.attributes is None:
            return
        self.tested_attribute = PROFILES[self.session.profile_id].attributes[index]
        self.action_roll()

    def action_roll(self) -> None:
        if self.pending_genre is not None:
            return
        try:
            result = self.session.roll(self.draft_request(), rng=self.rng)
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.show_result(result)
        self.update_strain_controls()
        self.log_result(result)
        self.update_tech_controls()
        if result.request.tech_target is not None and self.session.tech.remaining_bonus == 0:
            self.feedback(
                "Tech depleted: target cleared; initialize/replace explicitly to use again."
            )

    def action_reroll(self) -> None:
        if self.pending_genre is not None:
            return
        indices = self.selected_dice()
        try:
            result = self.session.reroll(indices, rng=self.rng)
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.show_result(result)
        self.log_result(result, f"Reroll dice {', '.join(str(i + 1) for i in sorted(indices))}")
