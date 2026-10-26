from collections.abc import Callable
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
    TextArea,
)
from textual.widgets.tabbed_content import ContentTabs

from wid.formatting import (
    attribute_label,
    corruption_status,
    pool_line,
    resources_line,
    resources_reminder,
    strain_status,
    strain_summary,
    tech_starting_line,
)
from wid.game import Game
from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import (
    RESOURCES_MAX,
    RESOURCES_MIN,
    BonusKind,
    PowerMode,
    ResourceEffect,
    RollResult,
    RollSession,
    StrainTracker,
)
from wid.sessions import CharacterDetails
from wid.settings import load_settings, save_settings
from wid.ui.dialogs import ConfirmReset, SpendResources
from wid.ui.outcomes import dice_content, summary_content
from wid.ui.sessions import SessionActions
from wid.ui.themes import DANGER, DANGER_THEME
from wid.ui.widgets import (
    CHARACTER_LABELS,
    TECH_SLOTS,
    AttributeRollButton,
    AttributeSetup,
    BonusButton,
    BonusName,
    CharacterGroup,
    GameRow,
    ItemsGroup,
    KitControls,
    ManifestationName,
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
    """The terminal front end: widgets that show the game and pass the player's actions to it."""

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
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self.register_theme(DANGER)
        self.layout: dict[str, object] = {}
        self.game = Game(rng=rng)
        # How many history entries the log shows, so only new ones are written.
        self.logged = 0
        self.pending_genre: Genre | None = None

    @property
    def session(self) -> RollSession:
        return self.game.session

    @property
    def history(self) -> list[HistoryEntry]:
        return self.game.history

    @property
    def tested_attribute(self) -> str:
        return self.game.tested_attribute

    @tested_attribute.setter
    def tested_attribute(self, attribute: str) -> None:
        self.game.tested_attribute = attribute

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
                    yield Button("Roll 1d6", id="roll-d6", tooltip="Roll one die outside a test")
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
        self.refresh_sheet()

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

    def collect(self) -> None:
        """Copy what the player typed, ticked or chose into the game before it acts."""
        game = self.game
        game.character = CharacterDetails.model_validate(
            {
                field: self.query_one(f"#character-{field}", Input).value
                for field in CHARACTER_LABELS
            }
        )
        game.name = self.query_one("#session-name", Input).value
        game.path = self.query_one("#session-path", Input).value
        game.notes = self.query_one("#session-notes", TextArea).text
        game.fear_level = self.query_one("#fear", Select).value
        game.assisted = self.query_one("#assisted", Checkbox).value
        game.expertise = self.query_one("#expertise", Checkbox).value
        game.power = self.chosen_power()
        game.reroll_selection = tuple(sorted(self.selected_dice()))
        target = self.query_one("#item-target", Select).value
        game.item_target = target if game.session.current_result is not None else None

    def act(self, action: Callable[[], str]) -> bool:
        """Run a game action, show its message or why it was refused, and refresh the screen."""
        self.collect()
        try:
            message = action()
        except ValueError as error:
            self.feedback(str(error))
            self.refresh_sheet()
            return False
        self.feedback(message)
        self.refresh_sheet()
        return True

    def refresh_sheet(self) -> None:
        """Bring every control up to date with the game."""
        self.show_draft()
        self.update_attribute_controls()
        self.update_kit_controls()
        self.update_strain_controls()
        result = self.session.current_result
        if result is None:
            self.clear_result_display()
        else:
            self.show_result(result)
        self.update_preview()
        self.write_new_history()

    def show_game(self) -> None:
        """Show a game that was replaced (loaded, a new character or kit), text fields included."""
        game = self.game
        with self.prevent(Input.Changed, Select.Changed):
            for field in CHARACTER_LABELS:
                self.query_one(f"#character-{field}", Input).value = getattr(game.character, field)
            self.query_one("#session-name", Input).value = game.name
            self.query_one("#session-path", Input).value = game.path
            self.query_one("#genre", Select).value = game.session.profile_id
            for field in self.query(BonusName):
                field.value = getattr(game.session.bonuses, field.kind)
            for field in self.query(PowerName):
                field.value = game.session.power_names[field.index]
            if game.session.attributes is None:
                for index in range(3):
                    self.query_one(f"#attribute-rank-{index}", Select).value = index + 1
        self.query_one("#session-notes", TextArea).load_text(game.notes)
        self.sub_title = game.name
        self.query_one("#log", RichLog).clear()
        self.logged = 0
        self.refresh_sheet()

    def show_draft(self) -> None:
        """Show the options for the next test, which a roll clears."""
        game = self.game
        with self.prevent(Select.Changed, Checkbox.Changed):
            self.query_one("#fear", Select).value = game.fear_level
            self.query_one("#assisted", Checkbox).value = game.assisted
            self.query_one("#expertise", Checkbox).value = game.expertise
            self.set_power(game.power)

    def write_new_history(self) -> None:
        log = self.query_one("#log", RichLog)
        if len(self.history) < self.logged:
            log.clear()
            self.logged = 0
        for entry in self.history[self.logged :]:
            log.write(str(entry))
        self.logged = len(self.history)

    def update_strain_controls(self) -> None:
        tracker = self.session.strain
        with self.prevent(Checkbox.Changed, Input.Changed):
            for box in self.query(StrainBox):
                box.sync(tracker)
            for field in self.query(StrainName):
                field.value = tracker.names[field.row]
        self.update_strain_status()

    def update_strain_status(self) -> None:
        tracker = self.session.strain
        self.query_one("#strain-section", Collapsible).title = strain_summary(tracker)
        self.query_one("#strain-status", Static).update(strain_status(tracker))

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
        self.query_one("#tech-attributes", Static).update(tech_starting_line(self.session.tech))

    def start_game(self) -> None:
        ranks = tuple(
            self.query_one(f"#attribute-rank-{index}", Select).value
            for index in range(len(PROFILES[self.session.profile_id].attributes))
        )
        self.act(lambda: self.game.start_game(ranks))

    def update_kit_controls(self) -> None:
        profile = PROFILES[self.session.profile_id]
        self.query_one("#powers").display = profile.has_powers
        # Tech replaces items, so a kit with Tech shows its slots in the same section.
        self.section("items").title = "Tech" if profile.has_tech else "Items"
        self.query_one("#item-rows").display = profile.uses_items
        self.query_one("#tech-controls").display = profile.has_tech
        self.query_one("#standing-field").display = profile.has_standing
        self.query_one("#resource-field").display = profile.has_resources
        self.query_one("#corruption-field").display = profile.has_rerolls
        self.update_corruption_controls()
        self.query_one("#crafted-row").display = profile.has_resources
        self.update_resource_controls()
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
            self.query_one(f"#apply-{kind}", Button).disabled = not self.game.bonus_available(kind)
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

    def update_corruption_controls(self) -> None:
        session = self.session
        names = session.manifestations
        self.query_one("#corruption-status", Label).update(corruption_status(session))
        with self.prevent(Input.Changed):
            for field in self.query(ManifestationName):
                field.disabled = field.index >= len(names)
                field.value = names[field.index] if field.index < len(names) else ""
        self.query_one("#add-manifestation", Button).disabled = session.succumbed
        self.query_one("#remove-manifestation", Button).disabled = not names

    def update_resource_controls(self) -> None:
        pool = self.session.resources
        self.query_one("#resource-count", Static).update(
            f"{pool} / {RESOURCES_MAX}" if pool is not None else "—"
        )
        self.query_one("#resources-down", Button).disabled = pool is None or pool <= RESOURCES_MIN
        self.query_one("#resources-up", Button).disabled = pool is None or pool >= RESOURCES_MAX
        self.query_one("#spend-resources", Button).disabled = pool != RESOURCES_MAX
        crafted = self.query_one(f"#name-{BonusKind.CRAFTED_ITEM}", Input)
        crafted.disabled = not self.session.item_crafted
        with self.prevent(Input.Changed):
            crafted.value = self.session.bonuses.crafted_item
        self.query_one("#lose-crafted-item", Button).disabled = not self.session.item_crafted

    def update_tech_controls(self) -> None:
        """Show one row per Tech slot; Use needs a roll, and both buttons a named, working piece."""
        owned = self.session.tech.pieces if self.session.tech is not None else ()
        for index in range(TECH_SLOTS):
            self.query_one(f"#tech-row-{index}").display = index < len(owned)
            if index >= len(owned):
                continue
            piece = owned[index]
            self.query_one(f"#tech-label-{index}", Label).update(
                f"Tech {index + 1} — strength {piece.strength}"
            )
            with self.prevent(Input.Changed):
                self.query_one(f"#tech-name-{index}", Input).value = piece.name
            self.query_one(f"#use-tech-{index}", Button).disabled = not self.game.tech_usable(index)
            working = piece.defined and piece.strength > 0
            self.query_one(f"#sacrifice-tech-{index}", Button).disabled = not working

    def request_genre(self, genre: Genre) -> None:
        if genre == self.session.profile_id or self.pending_genre is not None:
            return
        self.pending_genre = genre
        self.collect()
        if self.game.has_unsaved_state():
            self.push_screen(ConfirmReset(), self.finish_genre_change)
        else:
            self.finish_genre_change(True)

    def finish_genre_change(self, confirmed: bool) -> None:
        genre = self.pending_genre
        self.pending_genre = None
        if not confirmed or genre is None:
            self.query_one("#genre", Select).value = self.session.profile_id
            return
        message = self.game.change_kit(genre)
        self.show_game()
        self.feedback(message)

    def clear_result_display(self) -> None:
        self.query_one("#tested-attribute", Static).update("")
        self.query_one("#dice", Static).update("Roll a test to see individual outcomes.")
        self.query_one("#summary", Static).update("")
        self.query_one("#resources", Static).update("")

    def feedback(self, message: str) -> None:
        self.query_one("#feedback", Static).update(message)

    def chosen_power(self) -> PowerMode:
        return next(
            (toggle.mode for toggle in self.query(PowerToggle) if toggle.value), PowerMode.NONE
        )

    def set_power(self, mode: PowerMode) -> None:
        """Tick the toggle for ``mode`` and untick the other, since one power is used per roll."""
        for toggle in self.query(PowerToggle):
            toggle.value = toggle.mode == mode

    def update_preview(self) -> None:
        self.collect()
        self.query_one("#pool", Static).update(pool_line(self.game.draft_request(preview=True)))

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
            index, marked = event.checkbox.index, event.value
            self.act(lambda: self.game.set_strain_box(index, marked))
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
        elif isinstance(event.input, ManifestationName):
            self.session.set_manifestation_name(event.input.index, event.value)
        elif isinstance(event.input, TechName):
            self.session.set_tech_name(event.input.index, event.value)
            self.update_tech_controls()
        elif isinstance(event.input, BonusName):
            self.session.set_bonus_name(event.input.kind, event.value)
            self.update_bonus_controls()

    def on_standing_track_moved(self, event: StandingTrack.Moved) -> None:
        self.act(lambda: self.game.set_standing(event.standing))

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
            index = event.button.index
            self.act(lambda: self.game.sacrifice_tech(index))
            return
        game = self.game
        action = {
            "save-session": self.action_save_session,
            "export-history": self.action_export_history,
            "new-character": self.action_new_character,
            "load-session": self.action_load_session,
            "take-strain": lambda: self.act(game.take_strain),
            "take-wound": lambda: self.act(game.take_wound),
            "undo-bonus": lambda: self.act(game.undo_bonus),
            "toggle-history": self.action_toggle_history,
            "start-game": self.start_game,
            "reroll_button": self.action_reroll,
            "new-scenario": lambda: self.act(game.start_scenario),
            "resources-down": lambda: self.act(lambda: game.adjust_resources(-1)),
            "resources-up": lambda: self.act(lambda: game.adjust_resources(1)),
            "spend-resources": lambda: self.push_screen(SpendResources(), self.spend_resources),
            "lose-crafted-item": lambda: self.act(game.lose_crafted_item),
            "roll-d6": lambda: self.act(game.roll_one_die),
            "gain-corruption": self.gain_corruption,
            "add-manifestation": lambda: self.act(game.add_manifestation),
            "remove-manifestation": lambda: self.act(game.remove_manifestation),
        }.get(event.button.id)
        if action is not None:
            action()

    def apply_tech(self, index: int) -> None:
        if self.pending_genre is not None:
            return
        die = self.query_one("#item-target", Select).value
        self.act(lambda: self.game.apply_tech(index, die))

    def spend_resources(self, effect: ResourceEffect | None) -> None:
        if effect is not None:
            self.act(lambda: self.game.spend_resources(effect))

    def gain_corruption(self) -> None:
        amount = self.query_one("#corruption-amount", Select).value
        self.act(lambda: self.game.gain_corruption(amount))

    def apply_bonus(self, kind: BonusKind) -> None:
        if self.pending_genre is not None:
            return
        die = self.query_one("#item-target", Select).value
        self.act(lambda: self.game.apply_bonus(kind, die))

    def show_result(self, result: RollResult) -> None:
        variables = self.get_css_variables()
        tech = self.session.tech
        self.query_one("#dice", Static).update(dice_content(result, variables))
        self.query_one("#summary", Static).update(summary_content(result, variables))
        self.query_one("#tested-attribute", Static).update(attribute_label(result))
        self.query_one("#resources", Static).update(
            resources_line(
                result,
                total_strain=self.session.total_strain,
                total_corruption=self.session.total_corruption,
                tech_pieces=tech.pieces if tech else None,
            )
            + (f"\n{reminder}" if (reminder := resources_reminder(result)) else "")
        )
        with self.prevent(Checkbox.Changed):
            for box in self.query(RerollDie):
                box.value = box.index in self.game.reroll_selection
        self.update_reroll_controls()
        self.update_bonus_controls()

    def action_roll_attribute(self, index: int) -> None:
        if self.pending_genre is not None or self.session.attributes is None:
            return
        attribute = PROFILES[self.session.profile_id].attributes[index]
        self.act(lambda: self.game.roll(attribute))

    def action_roll(self) -> None:
        if self.pending_genre is not None:
            return
        self.act(self.game.roll)

    def action_reroll(self) -> None:
        if self.pending_genre is not None:
            return
        indices = self.selected_dice()
        self.act(lambda: self.game.reroll(indices))
