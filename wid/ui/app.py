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
    TextArea,
)

from wid.profiles import PROFILES, Genre
from wid.rolls import BonusKind, PowerMode, RollRequest, RollResult, RollSession
from wid.sessions import CharacterDetails, SavedSession, session_file_path
from wid.ui.dialogs import ConfirmReset, ConfirmSessionAction, LoadGame
from wid.ui.widgets import (
    BONUS_LABELS,
    CHARACTER_LABELS,
    OptionsGroup,
    ProfileGroup,
    RollerGroup,
    SessionGroup,
    StrainGroup,
)


class RollerApp(App):
    """Configure tests in widgets; resolve them through the session model."""

    CSS_PATH = "roller.tcss"
    TITLE = "We're in Danger"
    BINDINGS: ClassVar = [
        ("d", "toggle_dark", "Theme"),
        ("ctrl+r", "roll", "Repeat attribute"),
        ("ctrl+l", "toggle_history", "Log"),
    ]

    def __init__(self, *, rng: Random | None = None):
        super().__init__()
        self.rng = rng if rng is not None else Random()
        self.session = RollSession()
        self.history: list[str] = []
        self.pending_genre: Genre | None = None
        self.tested_attribute = PROFILES[Genre.CORE].attributes[0]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with VerticalScroll(id="configuration"):
                yield ProfileGroup()
                yield OptionsGroup()
                yield StrainGroup()
                yield SessionGroup()
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
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()

    def update_strain_controls(self) -> None:
        tracker = self.session.strain
        with self.prevent(Checkbox.Changed, Input.Changed):
            for index, checked in enumerate(tracker.boxes):
                self.query_one(f"#strain-box-{index}", Checkbox).value = checked
            for row, name in enumerate(tracker.names):
                self.query_one(f"#strain-name-{row}", Input).value = name
        self.update_strain_status()

    def update_strain_status(self) -> None:
        tracker = self.session.strain
        self.query_one("#strain-total", Label).update(
            f"Character strain: {sum(tracker.boxes)} / 12 marked"
        )
        status = "Check/uncheck any box to record harm, recovery, or corrections."
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
        return {
            index for index in range(7) if self.query_one(f"#reroll-die-{index}", Checkbox).value
        }

    def update_reroll_controls(self) -> None:
        enabled = PROFILES[self.session.profile_id].has_rerolls
        self.query_one("#reroll-controls").display = enabled
        result = self.session.current_result
        for index in range(7):
            checkbox = self.query_one(f"#reroll-die-{index}", Checkbox)
            available = enabled and result is not None and index < len(result.dice)
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
        self.query_one("#tested-attribute", Static).update("")
        self.query_one("#dice", Static).update("Roll a test to see individual outcomes.")
        self.query_one("#summary", Static).update("")
        self.query_one("#resources", Static).update("")
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()
        message = f"Switched to {PROFILES[genre].name}; active test cleared."
        self.feedback(message)
        self.history.append(message)
        self.query_one("#log", RichLog).write(message)

    def feedback(self, message: str) -> None:
        self.query_one("#feedback", Static).update(message)

    def session_path(self) -> Path:
        return session_file_path(self.query_one("#session-path", Input).value)

    def character_details(self) -> CharacterDetails:
        return CharacterDetails.model_validate(
            {
                field: self.query_one(f"#character-{field}", Input).value
                for field in CHARACTER_LABELS
            }
        )

    def action_save_session(self) -> None:
        if self.pending_genre is not None:
            return
        try:
            path = self.session_path()
            saved = SavedSession(
                name=self.query_one("#session-name", Input).value,
                session=self.session.model_copy(deep=True),
                draft=self.draft_request(),
                notes=self.query_one("#session-notes", TextArea).text,
                character=self.character_details(),
                history=tuple(self.history),
                reroll_indices=tuple(sorted(self.selected_dice())),
                item_target=(
                    self.query_one("#item-target", Select).value
                    if self.session.current_result is not None
                    else None
                ),
            )
            self.write_session(saved, path)
        except (OSError, ValueError) as error:
            self.feedback(f"Could not save session: {error}")

    def write_session(self, saved: SavedSession, path: Path, *, overwrite: bool = False) -> None:
        try:
            saved.save(path, overwrite=overwrite)
        except FileExistsError:
            self.push_screen(
                ConfirmSessionAction(f"Replace the existing save at {path}?"),
                lambda confirmed: self.finish_save(saved, path, confirmed),
            )
            return
        except (OSError, ValueError) as error:
            self.feedback(f"Could not save session: {error}")
            return
        self.query_one("#session-name", Input).value = saved.name
        self.sub_title = saved.name
        self.feedback(f"Saved {saved.name} to {path}.")

    def finish_save(self, saved: SavedSession, path: Path, confirmed: bool) -> None:
        if confirmed:
            self.write_session(saved, path, overwrite=True)
        else:
            self.feedback("Save canceled; existing file unchanged.")

    def action_load_session(self) -> None:
        if self.pending_genre is not None:
            return
        self.push_screen(
            LoadGame(self.query_one("#session-path", Input).value), self.load_session_path
        )

    def load_session_path(self, value: str | None) -> None:
        if value is None:
            return
        try:
            path = session_file_path(value)
            saved = SavedSession.load(path)
        except (OSError, ValueError) as error:
            self.feedback(f"Could not load session: {error}")
            return
        if (
            self.session.attributes is not None
            or self.history
            or self.query_one("#session-notes", TextArea).text
            or any(self.character_details().model_dump().values())
            or any(self.session.bonuses.model_dump().values())
            or self.has_resources()
        ):
            self.push_screen(
                ConfirmSessionAction(
                    f"Load {saved.name}? This replaces the current game and history. "
                    "Unsaved changes will be lost."
                ),
                lambda confirmed: self.finish_load(saved, path, confirmed),
            )
        else:
            self.finish_load(saved, path, True)

    def finish_load(self, saved: SavedSession, path: Path, confirmed: bool) -> None:
        if not confirmed:
            self.feedback("Load canceled; current game unchanged.")
            return
        self.session = saved.session.model_copy(deep=True)
        self.history = list(saved.history)
        draft = saved.draft
        with self.prevent(Select.Changed, Checkbox.Changed, Input.Changed):
            for field in CHARACTER_LABELS:
                self.query_one(f"#character-{field}", Input).value = getattr(saved.character, field)
            self.query_one("#genre", Select).value = self.session.profile_id
            self.tested_attribute = draft.attribute
            self.query_one("#fear", Select).value = draft.fear_level
            self.query_one("#power", Select).value = draft.power
            self.query_one("#assisted", Checkbox).value = draft.assisted
            self.query_one("#expertise", Checkbox).value = draft.expertise
            self.update_attribute_controls()
            self.update_preview()
            for kind in BonusKind:
                self.query_one(f"#name-{kind}", Input).value = getattr(self.session.bonuses, kind)
            self.query_one("#tech-target", Select).value = (
                draft.tech_target if draft.tech_target is not None else -1
            )
            self.update_kit_controls()
            if self.session.current_result is not None:
                self.show_result(self.session.current_result)
            else:
                self.query_one("#tested-attribute", Static).update("")
                self.query_one("#dice", Static).update("Roll a test to see individual outcomes.")
                self.query_one("#summary", Static).update("")
                self.query_one("#resources", Static).update("")
            for index in range(7):
                self.query_one(f"#reroll-die-{index}", Checkbox).value = (
                    index in saved.reroll_indices
                )
            self.update_reroll_controls()
            self.update_strain_controls()
            self.update_bonus_controls()
            if saved.item_target is not None:
                self.query_one("#item-target", Select).value = saved.item_target
        log = self.query_one("#log", RichLog)
        log.clear()
        for entry in self.history:
            log.write(entry)
        self.query_one("#session-name", Input).value = saved.name
        self.query_one("#session-path", Input).value = str(path)
        self.query_one("#session-notes", TextArea).load_text(saved.notes)
        self.sub_title = saved.name
        message = f"Loaded {saved.name} from {path}."
        if draft.item_allocations:
            message += " Legacy pre-roll item assignments cleared; apply named items after rolling."
        self.feedback(message)

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
        if event.checkbox.id and event.checkbox.id.startswith("strain-box-"):
            index = int(event.checkbox.id.removeprefix("strain-box-"))
            self.session.strain = self.session.strain.set_box(index, event.value)
            self.update_strain_status()
            return
        if event.checkbox.id == "assisted":
            self.update_preview()
        elif event.checkbox.id and event.checkbox.id.startswith("reroll-die-"):
            self.update_reroll_controls()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.value != event.input.value:
            return
        if event.input.id and event.input.id.startswith("strain-name-"):
            row = int(event.input.id.removeprefix("strain-name-"))
            self.session.strain = self.session.strain.set_name(row, event.value)
            self.update_strain_status()
        elif event.input.id and event.input.id.startswith("name-"):
            kind = BonusKind(event.input.id.removeprefix("name-"))
            self.session.set_bonus_name(kind, event.value)
            self.update_bonus_controls()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("roll-attribute-"):
            self.action_roll_attribute(int(event.button.id.removeprefix("roll-attribute-")))
            return
        if event.button.id and event.button.id.startswith("apply-"):
            self.apply_bonus(BonusKind(event.button.id.removeprefix("apply-")))
            return
        session_action = {
            "save-session": self.action_save_session,
            "load-session": self.action_load_session,
            "take-strain": self.take_strain,
            "toggle-history": self.action_toggle_history,
        }.get(event.button.id)
        if session_action is not None:
            session_action()
            return
        if event.button.id == "start-game":
            self.start_game()
            return
        if event.button.id == "reroll_button":
            self.action_reroll()
        elif event.button.id == "initialize-tech":
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
            self.history.append(message)
            self.query_one("#log", RichLog).write(message)

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

    @staticmethod
    def describe(result: RollResult) -> str:
        return "\n".join(
            f"Die {index + 1}: raw {die.raw} +{die.bonus} = {die.effective} — "
            f"{die.classify(result.request).value}"
            for index, die in enumerate(result.dice)
        )

    @staticmethod
    def summary(result: RollResult) -> str:
        totals = result.totals()
        return (
            f"Hits: {totals.hits} (dice {totals.dice_hits}, expertise {totals.expertise_hits}) | "
            f"Misses: {totals.misses} | Fumbles: {totals.fumbles}"
        )

    def show_result(self, result: RollResult) -> None:
        self.query_one("#dice", Static).update(
            "\n".join(
                f"{index + 1}: {die.raw}+{die.bonus}={die.effective} "
                f"{die.classify(result.request).value}"
                for index, die in enumerate(result.dice)
            )
        )
        self.query_one("#summary", Static).update(self.summary(result))
        self.query_one("#tested-attribute", Static).update(
            f"{result.request.attribute} (rank {result.request.attribute_rank})"
        )
        self.query_one("#resources", Static).update(
            f"Strain: +{result.strain_delta} (session {self.session.total_strain})"
            + (
                f" | Corruption: +{result.corruption_delta} "
                f"(session {self.session.total_corruption})"
                if PROFILES[result.request.profile_id].has_rerolls
                else ""
            )
            + (
                f" | Tech remaining: {self.session.tech.remaining_bonus}"
                if self.session.tech
                else ""
            )
        )
        for index in range(7):
            self.query_one(f"#reroll-die-{index}", Checkbox).value = False
        self.update_reroll_controls()
        self.update_bonus_controls()

    def log_result(
        self, result: RollResult, action: str = "Roll", *, resource_cost: bool = True
    ) -> None:
        request = result.request
        strain_delta = result.strain_delta if resource_cost else 0
        corruption_delta = result.corruption_delta if resource_cost else 0
        snapshot = (
            f"{action}: {request.profile_id.value}, {request.attribute} "
            f"rank {request.attribute_rank}; assisted={request.assisted}, "
            f"fear={request.fear_level}, expertise={request.expertise}, "
            f"power={request.power.value}, Tech target="
            f"{request.tech_target + 1 if request.tech_target is not None else 'none'}\n"
            + (f"Expertise name: {self.session.bonuses.expertise}\n" if request.expertise else "")
            + (
                f"{self.describe(result)}\n{self.summary(result)}\n"
                f"Strain +{strain_delta} (session {self.session.total_strain})"
            )
            + (
                f"; Corruption +{corruption_delta} (session {self.session.total_corruption})"
                if PROFILES[request.profile_id].has_rerolls
                else ""
            )
            + (f"; Tech remaining {self.session.tech.remaining_bonus}" if self.session.tech else "")
        )
        self.history.append(snapshot)
        self.query_one("#log", RichLog).write(snapshot)

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

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"
