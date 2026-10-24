from pathlib import Path

from textual.widgets import Checkbox, Input, RichLog, Select, TextArea

from wid.history import HistoryEntry
from wid.profiles import Genre
from wid.rolls import BonusKind, RollSession
from wid.sessions import CharacterDetails, SavedSession, session_file_path
from wid.ui.dialogs import ConfirmSessionAction, LoadGame
from wid.ui.widgets import CHARACTER_LABELS


class SessionActions:
    """Save, load, and character-detail handling for ``RollerApp``.

    A mixin: it relies on the app's widgets and update methods, and keeps file and
    dialog orchestration out of the main application module.
    """

    session: RollSession
    history: list[HistoryEntry]
    tested_attribute: str
    pending_genre: Genre | None

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
                self.clear_result_display()
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
            log.write(str(entry))
        self.query_one("#session-name", Input).value = saved.name
        self.query_one("#session-path", Input).value = str(path)
        self.query_one("#session-notes", TextArea).load_text(saved.notes)
        self.sub_title = saved.name
        message = f"Loaded {saved.name} from {path}."
        if draft.item_allocations:
            message += " Legacy pre-roll item assignments cleared; apply named items after rolling."
        self.feedback(message)
