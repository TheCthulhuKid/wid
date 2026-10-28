"""What the player's and the GM's terminal screens share: the theme and settings, the feedback
line, running a game action, the history log, the kit question and the command palette."""

from abc import abstractmethod
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from pathlib import Path
from random import Random
from typing import ClassVar

from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Select, Static

from wid.game import BaseGame, player_message
from wid.history import HistoryEntry, history_statistics
from wid.profiles import Genre
from wid.settings import load_settings, save_settings
from wid.ui.dialogs import SAVE_FIRST, Answer, Question
from wid.ui.themes import DANGER, DANGER_THEME
from wid.ui.widgets import HistoryPanel

# Below these sizes the panel switches to one-row controls and starts with sections collapsed.
SHORT_HEIGHT = 30
SMALL_WIDTH = 100

# A command in the palette: its title, its help text and the app method it runs.
PaletteCommand = tuple[str, str, Callable[["BaseApp"], object]]
# The three button tables of a screen: by widget type, by id for one game action, and by id
# for the handlers that open a dialog or need more than one game call.
ButtonTables = tuple[
    dict[type[Button], Callable[["BaseApp", Button], None]],
    dict[str, Callable[[BaseGame], str]],
    dict[str, Callable[["BaseApp"], None]],
]


class BaseApp(App):
    """A terminal front end: widgets that show a game and pass the actions to it.

    A mode composes its own panels, copies what was typed into its game (``collect``), redraws
    from it (``refresh_sheet`` and ``show_game``), and names its button tables, its palette
    commands and the answers of its kit question.
    """

    CSS_PATH = "roller.tcss"
    TITLE = "We're in Danger"
    KIT_QUESTION: ClassVar[str]
    KIT_ANSWERS: ClassVar[tuple[Answer, ...]]

    def __init__(
        self,
        *,
        rng: Random | None = None,
        settings_path: Path | None = None,
        recovery_path: Path | None = None,
        open_path: str | None = None,
    ):
        super().__init__()
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self.register_theme(DANGER)
        # Layout choices the user made, for a mode that remembers any.
        self.layout: dict[str, object] = {}
        self.game = self.make_game(rng, recovery_path)
        # A save named on the command line, opened once the screen is up.
        self.open_path = open_path
        # How many history entries the log shows, so only new ones are written.
        self.logged = 0
        self.pending_genre: Genre | None = None

    @abstractmethod
    def make_game(self, rng: Random | None, recovery_path: Path | None) -> BaseGame: ...

    @property
    @abstractmethod
    def genre(self) -> Genre:
        """The game's current kit."""

    @abstractmethod
    def compose_configuration(self) -> ComposeResult:
        """The left panel's widgets."""

    @abstractmethod
    def compose_output(self) -> ComposeResult:
        """The right panel's widgets."""

    @abstractmethod
    def collect(self) -> None:
        """Copy what the player typed, ticked or chose into the game before it acts."""

    @abstractmethod
    def refresh_sheet(self) -> None:
        """Bring every control up to date with the game; every change ends here."""

    @abstractmethod
    def show_game(self) -> None:
        """Show a game that was replaced (loaded, a new kit), text fields included."""

    @abstractmethod
    def change_kit(self, genre: Genre, answer: str) -> str | None:
        """Change the kit as the kit question's ``answer`` asks; None keeps the current kit."""

    @abstractmethod
    def button_tables(self) -> ButtonTables: ...

    @abstractmethod
    def palette_commands(self) -> Sequence[PaletteCommand]: ...

    @property
    def history(self) -> list[HistoryEntry]:
        return self.game.history

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with VerticalScroll(id="configuration"):
                yield from self.compose_configuration()
            with Vertical(id="output"):
                yield from self.compose_output()
        yield HistoryPanel(id="history-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.restore_theme()
        self.set_short_mode(self.size.height < SHORT_HEIGHT)
        self.restore_layout()
        self.refresh_sheet()
        if self.open_path:
            message = self.game.open_file(self.open_path)
            self.show_game()
            self.feedback(message)
        self.offer_recovery()

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
        """Apply the remembered layout, where a mode has one."""

    def restore_theme(self) -> None:
        self.theme = (
            self.settings.theme if self.settings.theme in self.available_themes else DANGER_THEME
        )
        self.watch(self, "theme", self.remember_theme, init=False)
        self.watch(self, "theme", self.redraw_for_theme, init=False)

    def redraw_for_theme(self) -> None:
        """Redraw what is coloured by the theme, where a mode has such a thing."""

    def remember_theme(self, theme: str) -> None:
        self.save_settings_change(theme=theme)

    def save_settings_change(self, **changes: object) -> None:
        self.settings = self.settings.model_copy(update=changes)
        try:
            save_settings(self.settings, self.settings_path)
        except OSError as error:
            self.feedback(f"Could not save settings: {error}")

    def feedback(self, message: str) -> None:
        self.query_one("#feedback", Static).update(message)

    def act(self, action: Callable[[], str]) -> bool:
        """Run a game action, show its message or why it was refused, and refresh the screen.

        Nothing runs while the kit-change dialog is open, since the game may be about to go.
        """
        if self.pending_genre is not None:
            return False
        self.collect()
        try:
            message = action()
        except ValueError as error:
            self.feedback(player_message(error))
            self.refresh_sheet()
            return False
        self.feedback(message)
        self.refresh_sheet()
        return True

    def finish_refresh(self) -> None:
        """The end of every ``refresh_sheet``: the log, Undo and the recovery copy."""
        self.write_new_history()
        self.query_one("#undo", Button).disabled = not self.game.can_undo
        # Every change ends here, so this is where the recovery copy follows the game.
        if warning := self.game.keep_recovery():
            self.feedback(warning)

    def write_new_history(self) -> None:
        """Add the entries the log does not show yet; ``show_game`` clears it for a new game."""
        log = self.query_one("#log", RichLog)
        for entry in self.history[self.logged :]:
            log.write(str(entry))
        self.logged = len(self.history)
        statistics = self.query_one("#history-statistics", Static)
        statistics.update(history_statistics(self.history))

    def clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()
        self.logged = 0

    def action_toggle_history(self) -> None:
        panel = self.query_one("#history-panel")
        toggle = self.query_one("#toggle-history", Button)
        if panel.display and self.query_one("#log").has_focus:
            toggle.focus()
        panel.display = not panel.display
        toggle.label = "Hide log" if panel.display else "Show log"

    def action_change_theme(self) -> None:
        self.search_themes()

    def request_genre(self, genre: Genre, *, offer_save: bool = True) -> None:
        """The kit selector changed: ask what to do with the game when it has unsaved changes.

        **Save first** saves, then asks again without that answer.
        """
        if genre == self.genre or self.pending_genre is not None:
            return
        self.pending_genre = genre
        self.collect()
        # With nothing to lose, the first answer is what the player would choose anyway.
        if not self.game.has_unsaved_state():
            self.finish_genre_change(self.KIT_ANSWERS[0].id)
            return
        answers = (SAVE_FIRST, *self.KIT_ANSWERS) if offer_save else self.KIT_ANSWERS
        self.push_screen(Question(self.KIT_QUESTION, answers), self.finish_genre_change)

    def finish_genre_change(self, answer: str) -> None:
        genre = self.pending_genre
        self.pending_genre = None
        if genre is None:
            return
        if answer == SAVE_FIRST.id:
            self.show_genre()
            self.action_save_session(then=lambda: self.request_genre(genre, offer_save=False))
            return
        message = self.change_kit(genre, answer)
        if message is None:
            self.show_genre()
            return
        self.show_game()
        self.feedback(message)

    def show_genre(self) -> None:
        with self.prevent(Select.Changed):
            self.query_one("#genre", Select).value = self.genre

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value != event.select.value:
            return
        if event.select.id == "genre" and event.value != Select.BLANK:
            self.request_genre(Genre(event.value))
        else:
            self.select_changed(event)

    def select_changed(self, event: Select.Changed) -> None:
        """A selector other than the kit changed, where a mode acts on one."""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        typed_buttons, game_buttons, app_buttons = self.button_tables()
        if (typed := typed_buttons.get(type(button))) is not None:
            typed(self, button)
        elif (action := game_buttons.get(button.id)) is not None:
            self.act(lambda: action(self.game))
        elif (handler := app_buttons.get(button.id)) is not None:
            handler(self)

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """The command palette (Ctrl+P): Textual's own commands, then the game's main actions.

        The game's actions are left out over a dialog, so none runs behind it or asks a second
        question on top of it.
        """
        yield from super().get_system_commands(screen)
        if screen is not self.screen_stack[0]:
            return
        for title, help_text, handler in self.palette_commands():
            yield SystemCommand(title, help_text, partial(handler, self))
