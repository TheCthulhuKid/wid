from pathlib import Path

from textual.widgets import Input, Select

from wid.formatting import (
    NEW_CHARACTER_QUESTION,
    QUIT_QUESTION,
    RECOVERY_QUESTION,
    load_question,
    recovery_decline,
    replace_question,
)
from wid.game import Game, player_message
from wid.profiles import Genre
from wid.sessions import SavedSession
from wid.ui.dialogs import ConfirmSessionAction, ExportHistory, LoadGame


class SessionActions:
    """The save, load, export, new-character and quit dialogs mixed into ``RollerApp``.

    The game does the work; these methods only ask the player to confirm and show the outcome.
    """

    game: Game
    pending_genre: Genre | None

    def action_save_session(self, overwrite: bool = False) -> None:
        try:
            done = self.act(lambda: self.game.save(overwrite=overwrite))
        except FileExistsError as error:
            self.push_screen(
                ConfirmSessionAction(replace_question("save", error.filename)),
                self.finish_save,
            )
            return
        if done:
            self.query_one("#session-name", Input).value = self.game.name
            self.sub_title = self.game.name

    def finish_save(self, confirmed: bool) -> None:
        if confirmed:
            self.action_save_session(overwrite=True)
        else:
            self.feedback("Save canceled; existing file unchanged.")

    def action_export_history(self) -> None:
        if self.pending_genre is not None:
            return
        self.collect()
        try:
            self.game.require_history()
        except ValueError as error:
            self.feedback(player_message(error))
            return
        self.push_screen(ExportHistory(self.game.default_export_path()), self.export_history_path)

    def export_history_path(self, value: str | None, overwrite: bool = False) -> None:
        if value is None:
            return
        try:
            self.act(lambda: self.game.export_history(value, overwrite=overwrite))
        except FileExistsError as error:
            self.push_screen(
                ConfirmSessionAction(replace_question("file", error.filename)),
                lambda confirmed: self.finish_export(value, confirmed),
            )

    def finish_export(self, value: str, confirmed: bool) -> None:
        if confirmed:
            self.export_history_path(value, overwrite=True)
        else:
            self.feedback("Export canceled; existing file unchanged.")

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
            self.feedback("New character canceled; current character unchanged.")
            return
        message = self.game.new_character()
        self.show_game()
        self.feedback(message)

    async def action_quit(self) -> None:
        """Ctrl+Q, which asks first when quitting would lose unsaved changes."""
        # Pressed again while the question is open, it would stack a second copy.
        if isinstance(self.screen, ConfirmSessionAction) and self.screen.message == QUIT_QUESTION:
            return
        # An open dialog covers the fields, and the action that opened it took them already.
        if self.screen is self.screen_stack[0]:
            self.collect()
        if self.game.has_unsaved_state():
            self.push_screen(ConfirmSessionAction(QUIT_QUESTION, "Quit"), self.finish_quit)
        else:
            self.exit()

    def finish_quit(self, confirmed: bool) -> None:
        if confirmed:
            # The player chose to lose the changes, so their recovery copy goes too.
            self.game.discard_recovery()
            self.exit()
        else:
            self.feedback("Quit canceled; the game is still open.")

    def offer_recovery(self) -> None:
        """On start, offer back the game an earlier run closed without saving."""
        if self.game.recovery_available():
            decline = recovery_decline(opened=bool(self.game.path))
            question = ConfirmSessionAction(RECOVERY_QUESTION, "Restore", decline)
            self.push_screen(question, self.finish_recovery)

    def finish_recovery(self, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            message = self.game.restore_recovery()
        except ValueError as error:
            self.feedback(player_message(error))
            return
        self.show_game()
        self.feedback(message)

    def action_load_session(self) -> None:
        if self.pending_genre is not None:
            return
        self.collect()
        self.push_screen(LoadGame(self.game.path), self.load_session_path)

    def load_session_path(self, value: str | None) -> None:
        if value is None:
            return
        try:
            saved, path = self.game.read_save(value)
        except ValueError as error:
            self.feedback(player_message(error))
            return
        if self.game.has_unsaved_state():
            self.push_screen(
                ConfirmSessionAction(load_question(saved.name)),
                lambda confirmed: self.finish_load(saved, path, confirmed),
            )
        else:
            self.finish_load(saved, path, True)

    def finish_load(self, saved: SavedSession, path: Path, confirmed: bool) -> None:
        if not confirmed:
            self.feedback("Load canceled; current game unchanged.")
            return
        message = self.game.load(saved, path)
        self.show_game()
        if saved.item_target is not None:
            with self.prevent(Select.Changed):
                self.query_one("#item-target", Select).value = saved.item_target
        self.feedback(message)
