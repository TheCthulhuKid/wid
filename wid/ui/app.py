from pathlib import Path
from random import Random
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Resize
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
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
from textual.widgets.tabbed_content import ContentTabs

from wid.formatting import attribute_label, resources_line, strain_summary
from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import (
    BonusKind,
    PowerMode,
    RollRequest,
    RollResult,
    RollSession,
    StrainTracker,
)
from wid.settings import load_settings, save_settings
from wid.ui.dialogs import ConfirmReset
from wid.ui.outcomes import dice_content, summary_content
from wid.ui.sessions import SessionActions
from wid.ui.themes import DANGER, DANGER_THEME
from wid.ui.widgets import (
    BONUS_LABELS,
    TECH_SLOTS,
    AttributeRollButton,
    AttributeSetup,
    BonusButton,
    BonusName,
    CharacterGroup,
    GameRow,
    ItemsGroup,
    KitControls,
    NotesGroup,
    PowerName,
    PowerToggle,
    RerollDie,
    RollerGroup,
    RollOptions,
    SacrificeButton,
    SessionFile,
    SessionName,
    StandingTrack,
    StrainBox,
    StrainGroup,
    StrainName,
    TechName,
    TechUseButton,
)

# Below these sizes the panel switches to one-row controls and starts with sections collapsed.
SHORT_HEIGHT = 30
SMALL_WIDTH = 100
TAB_NAMES = ("character", "session")
SECTION_NAMES = ("strain", "items")


class RollerApp(SessionActions, App):
    """Configure tests in widgets; resolve them through the session model."""

    CSS_PATH = "roller.tcss"
    TITLE = "We're in Danger"
    BINDINGS: ClassVar = [
        ("d", "change_theme", "Theme"),
        ("c", "show_tab('character')", "Character"),
        ("s", "show_tab('session')", "Session"),
        ("t", "toggle_section('strain')", "Strain"),
        ("i", "toggle_section('items')", "Items"),
        ("ctrl+r", "roll", "Repeat"),
        ("ctrl+l", "toggle_history", "Log"),
    ]

    def __init__(self, *, rng: Random | None = None, settings_path: Path | None = None):
        super().__init__()
        self.rng = rng if rng is not None else Random()
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self.register_theme(DANGER)
        self.layout: dict[str, object] = {}
        self.session = RollSession()
        self.history: list[HistoryEntry] = []
        self.pending_genre: Genre | None = None
        self.tested_attribute = PROFILES[Genre.CORE].attributes[0]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with VerticalScroll(id="configuration"):
                yield GameRow(id="profile-fields")
                with TabbedContent(id="details"):
                    with TabPane("Character", id="tab-character"):
                        yield CharacterGroup(id="character-fields")
                        yield AttributeSetup(id="attribute-setup")
                    with TabPane("Session", id="tab-session"):
                        yield SessionName()
                        yield NotesGroup()
                        yield SessionFile()
                yield RollOptions(id="test-options")
                yield KitControls()
                with Collapsible(title="Items", collapsed=False, id="items-section"):
                    yield ItemsGroup(id="items")
                with Collapsible(
                    title=strain_summary(StrainTracker()), collapsed=False, id="strain-section"
                ):
                    yield StrainGroup()
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
        self.query_one(Footer).compact = event.size.width < 90
        self.set_short_mode(event.size.height < SHORT_HEIGHT)

    def set_short_mode(self, short: bool) -> None:
        """In a short terminal, use one-row controls so more of the panel fits."""
        self.set_class(short, "short")
        controls = self.query_one("#configuration").query("Button, Input, Select, Checkbox")
        for control in controls.exclude(".strain-box, .strain-ending"):
            control.compact = short

    def restore_layout(self) -> None:
        """Apply the remembered tab and sections, or the defaults for this terminal size."""
        tabs = self.query_one("#details", TabbedContent)
        if self.settings.tab in TAB_NAMES:
            tabs.active = f"tab-{self.settings.tab}"
        small = self.size.width < SMALL_WIDTH or self.size.height < SHORT_HEIGHT
        for name in SECTION_NAMES:
            remembered = getattr(self.settings, f"{name}_collapsed")
            self.section(name).collapsed = small if remembered is None else remembered
        self.layout = {"tab": tabs.active.removeprefix("tab-")} | {
            f"{name}_collapsed": self.section(name).collapsed for name in SECTION_NAMES
        }

    def section(self, name: str) -> Collapsible:
        return self.query_one(f"#{name}-section", Collapsible)

    def remember_layout(self, key: str, value: object) -> None:
        """Save a layout choice the user made; changes made while starting up are not saved."""
        if key not in self.layout or self.layout[key] == value:
            return
        self.layout[key] = value
        self.save_settings_change(**{key: value})

    def on_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        self.remember_section(event.collapsible)

    def on_collapsible_collapsed(self, event: Collapsible.Collapsed) -> None:
        self.remember_section(event.collapsible)

    def remember_section(self, section: Collapsible) -> None:
        name = (section.id or "").removesuffix("-section")
        if name in SECTION_NAMES:
            self.remember_layout(f"{name}_collapsed", section.collapsed)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # The tab bar's current value, not the event's: a startup event can arrive late.
        self.remember_layout("tab", event.tabbed_content.active.removeprefix("tab-"))

    def action_show_tab(self, name: str) -> None:
        tabs = self.query_one("#details", TabbedContent)
        tabs.active = f"tab-{name}"
        # Focus the tab bar, not a field: letters typed in a field would swallow the shortcuts.
        tabs.query_one(ContentTabs).focus()

    def action_toggle_section(self, name: str) -> None:
        section = self.section(name)
        section.collapsed = not section.collapsed
        if section.collapsed:
            section.query_one("CollapsibleTitle").focus()

    def action_toggle_history(self) -> None:
        panel = self.query_one("#history-panel")
        toggle = self.query_one("#toggle-history", Button)
        if panel.display and self.query_one("#log").has_focus:
            toggle.focus()
        panel.display = not panel.display
        toggle.label = "Hide log" if panel.display else "Show log"

    def on_mount(self) -> None:
        self.restore_theme()
        self.set_short_mode(self.size.height < SHORT_HEIGHT)
        self.restore_layout()
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()

    def restore_theme(self) -> None:
        self.theme = (
            self.settings.theme if self.settings.theme in self.available_themes else DANGER_THEME
        )
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
        self.save_settings_change(theme=theme)

    def save_settings_change(self, **changes: object) -> None:
        self.settings = self.settings.model_copy(update=changes)
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
        self.query_one("#strain-section", Collapsible).title = strain_summary(tracker)
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
        self.query_one("#new-scenario", Button).disabled = not ready
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
        tech = self.session.tech
        self.query_one("#tech-attributes", Static).update(
            f"Each piece starts at Science {tech.science} + Culture {tech.culture} = "
            f"{tech.starting_strength}."
            if tech is not None
            else "Start the game to get your Tech slots."
        )

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
        self.update_tech_controls()
        self.feedback("Attributes set for this game; press Roll beside an attribute.")

    def update_kit_controls(self) -> None:
        profile = PROFILES[self.session.profile_id]
        self.query_one("#powers").display = profile.has_powers
        # Tech replaces items, so a kit with Tech shows its slots in the same section.
        self.section("items").title = "Tech" if profile.has_tech else "Items"
        self.query_one("#item-rows").display = profile.uses_items
        self.query_one("#tech-controls").display = profile.has_tech
        self.query_one("#standing-field").display = profile.has_standing
        self.query_one(StandingTrack).standing = self.session.standing
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
            elif result is not None:
                available = available and kind not in result.applied_items
            self.query_one(f"#apply-{kind}", Button).disabled = not available
        self.query_one("#undo-bonus", Button).disabled = not self.session.can_undo_bonus
        self.update_tech_controls()

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
        """Show one row per Tech slot; Use needs a roll, and both buttons a named, working piece."""
        owned = self.session.tech.pieces if self.session.tech is not None else ()
        result = self.session.current_result
        for index in range(TECH_SLOTS):
            self.query_one(f"#tech-row-{index}").display = index < len(owned)
            if index >= len(owned):
                continue
            piece = owned[index]
            working = piece.defined and piece.strength > 0
            self.query_one(f"#tech-label-{index}", Label).update(
                f"Tech {index + 1} — strength {piece.strength}"
            )
            self.query_one(f"#use-tech-{index}", Button).disabled = not (
                working and result is not None and index not in result.applied_tech
            )
            self.query_one(f"#sacrifice-tech-{index}", Button).disabled = not working

    def has_resources(self) -> bool:
        return bool(
            self.session.total_strain
            or self.session.total_corruption
            or any(self.session.strain.boxes)
            or any(self.session.strain.names)
        )

    def request_genre(self, genre: Genre) -> None:
        if genre == self.session.profile_id or self.pending_genre is not None:
            return
        self.pending_genre = genre
        if self.has_unsaved_state():
            self.push_screen(ConfirmReset(), self.finish_genre_change)
        else:
            self.finish_genre_change(True)

    def finish_genre_change(self, confirmed: bool) -> None:
        genre = self.pending_genre
        self.pending_genre = None
        if not confirmed or genre is None:
            self.query_one("#genre", Select).value = self.session.profile_id
            return
        self.start_new_game(genre)

    def start_fresh_session(self, session: RollSession) -> None:
        """Replace the game with ``session`` and reset the controls that belong to a test."""
        self.session = session
        self.set_power(PowerMode.NONE)
        self.tested_attribute = PROFILES[session.profile_id].attributes[0]
        for index in range(3):
            self.query_one(f"#attribute-rank-{index}", Select).value = index + 1
        self.clear_result_display()
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_preview()
        self.update_strain_controls()

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
                self.chosen_power()
                if PROFILES[self.session.profile_id].has_powers
                else PowerMode.NONE
            ),
        )

    def chosen_power(self) -> PowerMode:
        return next(
            (toggle.mode for toggle in self.query(PowerToggle) if toggle.value), PowerMode.NONE
        )

    def set_power(self, mode: PowerMode) -> None:
        """Tick the toggle for ``mode`` and untick the other, since one power is used per roll."""
        for toggle in self.query(PowerToggle):
            toggle.value = toggle.mode == mode

    def update_preview(self) -> None:
        request = self.draft_request(preview=True)
        size = request.pool_size()
        self.query_one("#pool", Static).update(f"Pool: {size}d6 — hits on {request.hit_threshold}+")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != event.select.value:
            return
        if event.select.id == "genre" and event.value != Select.BLANK:
            self.request_genre(Genre(event.value))
        elif event.select.id == "fear":
            self.update_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.value != event.checkbox.value:
            return
        if isinstance(event.checkbox, StrainBox):
            self.change_strain_box(event.checkbox.index, event.value)
        elif isinstance(event.checkbox, PowerToggle):
            if event.value:
                self.set_power(event.checkbox.mode)
            self.update_preview()
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
        elif isinstance(event.input, PowerName):
            self.session.set_power_name(event.input.index, event.value)
        elif isinstance(event.input, TechName):
            self.session.set_tech_name(event.input.index, event.value)
            self.update_tech_controls()
        elif isinstance(event.input, BonusName):
            self.session.set_bonus_name(event.input.kind, event.value)
            self.update_bonus_controls()

    def on_standing_track_moved(self, event: StandingTrack.Moved) -> None:
        try:
            self.session.set_standing(event.standing)
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.query_one(StandingTrack).standing = self.session.standing

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, AttributeRollButton):
            self.action_roll_attribute(event.button.index)
            return
        if isinstance(event.button, BonusButton):
            self.apply_bonus(event.button.kind)
            return
        if isinstance(event.button, TechUseButton):
            self.apply_tech(event.button.index)
            return
        if isinstance(event.button, SacrificeButton):
            self.sacrifice_tech(event.button.index)
            return
        action = {
            "save-session": self.action_save_session,
            "export-history": self.action_export_history,
            "new-character": self.action_new_character,
            "load-session": self.action_load_session,
            "take-strain": self.take_strain,
            "take-wound": self.take_wound,
            "undo-bonus": self.undo_bonus,
            "toggle-history": self.action_toggle_history,
            "start-game": self.start_game,
            "reroll_button": self.action_reroll,
            "new-scenario": self.start_scenario,
        }.get(event.button.id)
        if action is not None:
            action()

    def start_scenario(self) -> None:
        try:
            tech = self.session.start_scenario()
        except ValueError as error:
            self.feedback(str(error))
            return
        with self.prevent(Input.Changed):
            for field in self.query(TechName):
                field.value = ""
        self.update_bonus_controls()
        message = f"New scenario: {len(tech.pieces)} empty Tech slot(s)."
        self.feedback(message)
        self.record(HistoryEntry(notice=message))

    def sacrifice_tech(self, index: int) -> None:
        try:
            piece = self.session.sacrifice_tech(index)
        except ValueError as error:
            self.feedback(str(error))
            return
        self.update_bonus_controls()
        message = f"Sacrificed {piece.label(index)}: strength {piece.strength} → 0."
        self.feedback(message)
        self.record(HistoryEntry(notice=message))

    def apply_tech(self, index: int) -> None:
        if self.pending_genre is not None:
            return
        piece = self.session.tech.pieces[index]
        die = self.query_one("#item-target", Select).value
        try:
            result = self.session.apply_tech(index, die)
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.show_result(result)
        action = f"Tech {piece.label(index)}: +{piece.strength} to die {die + 1}"
        self.log_result(result, action, resource_cost=False)

    def take_strain(self) -> None:
        self.session.strain = self.session.strain.take(1)
        self.update_strain_controls()

    def take_wound(self) -> None:
        try:
            self.session.strain = self.session.strain.take_wound()
        except ValueError as error:
            self.feedback(str(error))
        self.update_strain_controls()

    def undo_bonus(self) -> None:
        try:
            result = self.session.undo_bonus()
        except ValueError as error:
            self.feedback(str(error))
            return
        self.feedback("")
        self.show_result(result)
        self.log_result(result, "Undo last bonus", resource_cost=False)

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
                tech_pieces=tech.pieces if tech else None,
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
                tech_pieces=tech.pieces if tech else None,
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
        self.clear_roll_bonuses()

    def clear_roll_bonuses(self) -> None:
        """Assisted, Expertise and a power apply to one test; the next one starts without them."""
        for selector in ("#assisted", "#expertise"):
            self.query_one(selector, Checkbox).value = False
        self.set_power(PowerMode.NONE)

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
