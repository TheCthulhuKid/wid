from collections.abc import Callable, Sequence
from operator import attrgetter
from pathlib import Path
from random import Random
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.tabbed_content import ContentTabs

from wid.formatting import (
    CHARACTER_LABELS,
    NEW_CHARACTER_QUESTION,
    NEW_GAME_QUESTION,
    NO_RESULT_HINT,
    RANKS_HINT,
    attribute_label,
    corruption_status,
    pool_line,
    resources_line,
    resources_reminder,
    result_text,
    strain_status,
    strain_summary,
    tech_slot_label,
    tech_starting_line,
)
from wid.game import Game, NameField
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
from wid.ui.base import SHORT_HEIGHT, SMALL_WIDTH, BaseApp, ButtonTables, PaletteCommand
from wid.ui.dialogs import CANCEL, CONFIRM, Answer, ConfirmSessionAction, SpendResources
from wid.ui.outcomes import dice_content, summary_content
from wid.ui.sessions import SessionActions
from wid.ui.widgets import (
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

TAB_NAMES = ("character", "session")
SECTION_NAMES = ("strain", "items")

# Buttons that run one game action and show what it says.
GAME_BUTTONS: dict[str, Callable[[Game], str]] = {
    "take-strain": Game.take_strain,
    "take-wound": Game.take_wound,
    "undo": Game.undo,
    "new-scenario": Game.start_scenario,
    "resources-down": lambda game: game.adjust_resources(-1),
    "resources-up": lambda game: game.adjust_resources(1),
    "lose-crafted-item": Game.lose_crafted_item,
    "roll-d6": Game.roll_one_die,
    "add-manifestation": Game.add_manifestation,
    "remove-manifestation": Game.remove_manifestation,
}


class RollerApp(SessionActions, BaseApp):
    """The player's terminal screen: the character sheet, with the rolls on the right."""

    KIT_QUESTION = NEW_GAME_QUESTION
    KIT_ANSWERS = (
        Answer(CONFIRM, "Start new game", "warning"),
        Answer(CANCEL, "Keep current game"),
    )
    BINDINGS: ClassVar = [
        ("d", "change_theme", "Theme"),
        ("c", "show_tab('character')", "Character"),
        ("s", "show_tab('session')", "Session"),
        ("t", "toggle_section('strain')", "Strain"),
        ("i", "toggle_section('items')", "Items"),
        ("ctrl+r", "roll", "Repeat"),
        ("ctrl+l", "toggle_history", "Log"),
    ]

    def make_game(self, rng: Random | None, recovery_path: Path | None) -> Game:
        return Game(rng=rng, recovery_path=recovery_path)

    @property
    def session(self) -> RollSession:
        return self.game.session

    @property
    def genre(self) -> Genre:
        return self.session.profile_id

    def compose_configuration(self) -> ComposeResult:
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

    def compose_output(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("Show log", id="toggle-history")
            yield Button("Roll 1d6", id="roll-d6", tooltip="Roll one die outside a test")
        yield Static(id="feedback", markup=False)
        yield RollerGroup()

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

    def redraw_for_theme(self) -> None:
        result = self.session.current_result
        if result is None:
            return
        variables = self.get_css_variables()
        self.query_one("#dice", Static).update(dice_content(result, variables))
        self.query_one("#summary", Static).update(summary_content(result, variables))

    def collect(self) -> None:
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
        game.set_test_options(
            fear_level=self.query_one("#fear", Select).value,
            assisted=self.query_one("#assisted", Checkbox).value,
            expertise=self.query_one("#expertise", Checkbox).value,
            power=self.chosen_power(),
            reroll=self.selected_dice(),
            item_target=self.query_one("#item-target", Select).value,
        )

    def refresh_sheet(self) -> None:
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
        self.query_one("#copy-result", Button).disabled = self.session.current_result is None
        self.finish_refresh()

    def show_game(self) -> None:
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
        self.clear_log()
        self.refresh_sheet()
        # The die an item was aimed at, once the selector has the dice of the shown result.
        if game.item_target is not None:
            with self.prevent(Select.Changed):
                self.query_one("#item-target", Select).value = game.item_target

    def show_draft(self) -> None:
        """Show the options for the next test, which a roll clears."""
        game = self.game
        with self.prevent(Select.Changed, Checkbox.Changed):
            self.query_one("#fear", Select).value = game.fear_level
            self.query_one("#assisted", Checkbox).value = game.assisted
            self.query_one("#expertise", Checkbox).value = game.expertise
            self.set_power(game.power)

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
            "Roll beside an attribute to test it." if ready else RANKS_HINT
        )
        self.query_one("#start-game", Button).display = not ready
        self.query_one("#new-scenario", Button).disabled = not ready
        for index, attribute in enumerate(attributes):
            selector = self.query_one(f"#attribute-rank-{index}", Select)
            button = self.query_one(f"#roll-attribute-{index}", Button)
            self.query_one(f"#attribute-label-{index}", Label).update(attribute)
            selector.disabled = ready
            button.disabled = not ready
            button.tooltip = f"Roll {attribute}"
            if ready:
                selector.value = self.session.attribute_rank(attribute)
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
                tech_slot_label(index, piece.strength)
            )
            with self.prevent(Input.Changed):
                self.query_one(f"#tech-name-{index}", Input).value = piece.name
            self.query_one(f"#use-tech-{index}", Button).disabled = not self.game.tech_usable(index)
            self.query_one(f"#sacrifice-tech-{index}", Button).disabled = not piece.working

    def change_kit(self, genre: Genre, answer: str) -> str | None:
        return self.game.change_kit(genre) if answer == CONFIRM else None

    def action_new_character(self) -> None:
        if self.pending_genre is not None:
            return
        self.collect()
        if self.game.has_unsaved_state():
            self.push_screen(
                ConfirmSessionAction(NEW_CHARACTER_QUESTION),
                self.finish_new_character,
            )
        else:
            self.finish_new_character(True)

    def finish_new_character(self, confirmed: bool) -> None:
        if not confirmed:
            self.feedback("New character cancelled; current character unchanged.")
            return
        message = self.game.new_character()
        self.show_game()
        self.feedback(message)

    def clear_result_display(self) -> None:
        self.query_one("#tested-attribute", Static).update("")
        self.query_one("#dice", Static).update(NO_RESULT_HINT)
        self.query_one("#summary", Static).update("")
        self.query_one("#resources", Static).update("")

    def chosen_power(self) -> PowerMode:
        return next(
            (toggle.mode for toggle in self.query(PowerToggle) if toggle.value), PowerMode.NONE
        )

    def set_power(self, mode: PowerMode) -> None:
        """Tick the toggle for ``mode`` and untick the other, since one power is used per roll."""
        for toggle in self.query(PowerToggle):
            toggle.value = toggle.mode == mode

    def update_preview(self) -> None:
        self.query_one("#pool", Static).update(pool_line(self.game.draft_request(preview=True)))

    def options_changed(self) -> None:
        """Scared, Assisted or a power changed: the game takes it, and the pool line follows."""
        self.collect()
        self.update_preview()

    def select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "fear":
            self.options_changed()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        checkbox = event.checkbox
        if event.value != checkbox.value:
            return
        handler = CHECKBOXES.get(checkbox.id) or CHECKBOXES.get(type(checkbox))
        if handler is not None:
            handler(self, checkbox)

    def mark_strain_box(self, box: StrainBox) -> None:
        index, marked = box.index, box.value
        self.act(lambda: self.game.set_strain_box(index, marked))

    def use_power(self, toggle: PowerToggle) -> None:
        if toggle.value:
            self.set_power(toggle.mode)
        self.options_changed()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.value != event.input.value:
            return
        name_field = NAME_FIELDS.get(type(event.input))
        if name_field is None:
            return
        field, slot, refresh = name_field
        self.game.rename(field, slot(event.input), event.value)
        if refresh is not None:
            refresh(self)

    def on_standing_track_moved(self, event: StandingTrack.Moved) -> None:
        self.act(lambda: self.game.set_standing(event.standing))

    def button_tables(self) -> ButtonTables:
        return TYPED_BUTTONS, GAME_BUTTONS, APP_BUTTONS

    def palette_commands(self) -> Sequence[PaletteCommand]:
        return PALETTE_COMMANDS

    def copy_result(self) -> None:
        """Copy the shown result as text, for pasting into a chat; most terminals pass it on."""
        result = self.session.current_result
        if result is None:
            return
        self.copy_to_clipboard(result_text(result))
        self.feedback("Copied the result.")

    def ask_spend_resources(self) -> None:
        self.push_screen(SpendResources(), self.spend_resources)

    def apply_tech(self, index: int) -> None:
        die = self.query_one("#item-target", Select).value
        self.act(lambda: self.game.apply_tech(index, die))

    def spend_resources(self, effect: ResourceEffect | None) -> None:
        if effect is not None:
            self.act(lambda: self.game.spend_resources(effect))

    def gain_corruption(self) -> None:
        amount = self.query_one("#corruption-amount", Select).value
        self.act(lambda: self.game.gain_corruption(amount))

    def apply_bonus(self, kind: BonusKind) -> None:
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
        attribute = PROFILES[self.session.profile_id].attributes[index]
        self.act(lambda: self.game.roll(attribute))

    def action_roll(self) -> None:
        self.act(self.game.roll)

    def action_reroll(self) -> None:
        indices = self.selected_dice()
        self.act(lambda: self.game.reroll(indices))


# The tables below name RollerApp's methods, so they follow the class.

# Checkboxes by id, or else by type, and what changing one does.
CHECKBOXES: dict[str | type[Checkbox], Callable[[RollerApp, Checkbox], None]] = {
    StrainBox: RollerApp.mark_strain_box,
    PowerToggle: RollerApp.use_power,
    "assisted": lambda app, checkbox: app.options_changed(),
    RerollDie: lambda app, checkbox: app.update_reroll_controls(),
}

# Each name field: the game name it changes, its slot there, and the controls that show it.
NAME_FIELDS: dict[
    type[Input], tuple[NameField, Callable[[Input], object], Callable[[RollerApp], None] | None]
] = {
    BonusName: ("bonus", attrgetter("kind"), RollerApp.update_bonus_controls),
    PowerName: ("power", attrgetter("index"), None),
    ManifestationName: ("manifestation", attrgetter("index"), None),
    TechName: ("tech", attrgetter("index"), RollerApp.update_tech_controls),
    StrainName: ("strain", attrgetter("row"), RollerApp.update_strain_status),
}

# Buttons that stand for one slot of the sheet, by type.
TYPED_BUTTONS: dict[type[Button], Callable[[RollerApp, Button], None]] = {
    AttributeRollButton: lambda app, button: app.action_roll_attribute(button.index),
    BonusButton: lambda app, button: app.apply_bonus(button.kind),
    TechUseButton: lambda app, button: app.apply_tech(button.index),
    SacrificeButton: lambda app, button: app.act(lambda: app.game.sacrifice_tech(button.index)),
}

# The game's actions in the command palette, beside the buttons that run the same handlers.
PALETTE_COMMANDS: tuple[PaletteCommand, ...] = (
    ("Save session", "Save the game to the session file", RollerApp.action_save_session),
    ("Load session", "Open a saved session", RollerApp.action_load_session),
    (
        "Export history",
        "Write the sheet, notes and history to a Markdown file",
        RollerApp.action_export_history,
    ),
    ("New character", "Start a new character in the same kit", RollerApp.action_new_character),
    ("Undo", "Take back the last change to the sheet", lambda app: app.act(app.game.undo)),
    ("Copy result", "Copy the dice as text", RollerApp.copy_result),
)

# The other buttons, by id, that open a dialog or need more than one game call.
APP_BUTTONS: dict[str, Callable[[RollerApp], None]] = {
    "copy-result": RollerApp.copy_result,
    "save-session": RollerApp.action_save_session,
    "export-history": RollerApp.action_export_history,
    "new-character": RollerApp.action_new_character,
    "load-session": RollerApp.action_load_session,
    "toggle-history": RollerApp.action_toggle_history,
    "start-game": RollerApp.start_game,
    "reroll_button": RollerApp.action_reroll,
    "spend-resources": RollerApp.ask_spend_resources,
    "gain-corruption": RollerApp.gain_corruption,
}
