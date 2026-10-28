from collections.abc import Callable
from pathlib import Path

from textual.widgets import Input

from wid.formatting import (
    QUIT_QUESTION,
    RECOVERY_QUESTION,
    load_question,
    recovery_decline,
    replace_question,
)
from wid.game import BaseGame, player_message
from wid.profiles import Genre
from wid.sessions import SaveFile
from wid.ui.dialogs import ConfirmSessionAction, ExportHistory, LoadGame


class SessionActions:
    """The save, load, export and quit dialogs mixed into both terminal apps.

    The game does the work; these methods only ask the player to confirm and show the outcome.
    """

    game: BaseGame
    pending_genre: Genre | None

    def action_save_session(
        self, overwrite: bool = False, then: Callable[[], None] | None = None
    ) -> None:
        """Save; ``then`` runs once the save is done, after any question about replacing."""
        try:
            done = self.act(lambda: self.game.save(overwrite=overwrite))
        except FileExistsError as error:
            self.push_screen(
                ConfirmSessionAction(replace_question("save", error.filename)),
                lambda confirmed: self.finish_save(confirmed, then),
            )
            return
        if done:
            self.query_one("#session-name", Input).value = self.game.name
            self.sub_title = self.game.name
            if then is not None:
                then()

    def finish_save(self, confirmed: bool, then: Callable[[], None] | None = None) -> None:
        if confirmed:
            self.action_save_session(overwrite=True, then=then)
        else:
            self.feedback("Save cancelled; existing file unchanged.")

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
            self.feedback("Export cancelled; existing file unchanged.")

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
            self.feedback("Quit cancelled; the game is still open.")

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

    def finish_load(self, saved: SaveFile, path: Path, confirmed: bool) -> None:
        if not confirmed:
            self.feedback("Load cancelled; current game unchanged.")
            return
        message = self.game.load(saved, path)
        self.show_game()
        self.feedback(message)
