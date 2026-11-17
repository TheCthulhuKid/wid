"""What every mode shares: the history, the session name, notes and file path, Undo, saving,
loading, exporting and the recovery copy.

Each action returns the feedback to show (empty when there is nothing to say), and a refused
action raises ``ValueError`` with a message for the player. Saving and exporting raise
``FileExistsError`` (with the target in ``filename``) when they would replace a file, so the
front end can ask before calling again with ``overwrite=True``. History entries are appended
here, so front ends only display ``history``.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from random import Random
from typing import Any, NamedTuple

from pydantic import BaseModel, ValidationError

from wid.export import history_markdown
from wid.history import HistoryEntry, history_statistics
from wid.profiles import WiDProfile
from wid.rolls import roll_d6
from wid.sessions import NAME_MAX, CharacterDetails, Recovery, session_file_path
from wid.storage import write_text


def player_message(error: Exception) -> str:
    """The reason to show the player: pydantic's first message, without its prefix."""
    if isinstance(error, ValidationError):
        return error.errors()[0]["msg"].removeprefix("Value error, ")
    # An OS error reads "No such file or directory: game.json", without Python's "[Errno 2]".
    if isinstance(error, OSError) and error.strerror:
        return f"{error.strerror}: {error.filename}" if error.filename else error.strerror
    return str(error)


# The name a game without one is kept under, in the recovery copy and a browser download.
UNNAMED = "Unsaved game"
UNDO_LIMIT = 10


@contextmanager
def reported(what: str) -> Iterator[None]:
    """Turn a file or save error into "Could not {what}: ..." for the player.

    ``FileExistsError`` goes through as it is, so the front end can ask before replacing.
    """
    try:
        yield
    except FileExistsError:
        raise
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not {what}: {player_message(error)}") from error


class Before(NamedTuple):
    """The game just before a change, and the change's name for "Undid the last ..."."""

    change: str
    state: BaseModel
    # The names just after the change, to tell which the player typed since.
    names: dict[Any, str]
    # What ``options()`` held, for a change that resets them; None otherwise.
    options: Any


class BaseGame(ABC):
    """What every mode shares. A mode supplies its state (``state``, the names typed into it,
    ``restore``), what a save keeps (``snapshot``, ``saved_session``, ``parse_save``,
    ``take_over``) and the sheet an export lists."""

    def __init__(self, *, rng: Random | None = None, recovery_path: Path | None = None):
        self.rng = rng if rng is not None else Random()
        self.history: list[HistoryEntry] = []
        self.name = ""
        self.path = ""
        self.notes = ""
        self.undo_stack: list[Before] = []
        # What the last save or load held, to tell whether anything has changed since.
        self.saved_snapshot: dict[str, object] | None = None
        # Where unsaved changes are kept in case wid closes; None keeps no copy (as in tests).
        self.recovery_path = recovery_path
        # What this run last wrote there, so an unchanged game is not written again.
        self.recovery_snapshot: dict[str, object] | None = None
        self.recovery_failed = False

    @property
    @abstractmethod
    def state(self) -> BaseModel:
        """The model Undo copies before a change and puts back after."""

    @property
    @abstractmethod
    def profile(self) -> WiDProfile:
        """The genre kit the game is played in."""

    @property
    @abstractmethod
    def in_play(self) -> bool:
        """Whether the state has anything to lose, apart from the history and typed text."""

    @property
    def savable(self) -> bool:
        """Whether the state can go into a save file yet."""
        return True

    @abstractmethod
    def typed_names(self, state: BaseModel) -> dict[Any, str]:
        """The names the player types into ``state``, by slot, kept across an undo."""

    @abstractmethod
    def restore(self, state: BaseModel, names: dict[Any, str], action: str) -> None:
        """Put ``state`` back with ``names`` typed into it, and log ``action``."""

    def options(self) -> Any:
        """What an undoable change made with ``options=True`` also puts back."""
        return ()

    def restore_options(self, options: Any) -> None:
        """Put back what ``options`` kept; nothing, unless the mode has options."""

    @abstractmethod
    def saved_session(self, name: str) -> BaseModel:
        """The game as a save file holds it, under ``name``."""

    @abstractmethod
    def parse_save(self, text: str) -> BaseModel:
        """A save of this mode from its JSON; a ``ValueError`` says why one cannot be read."""

    @abstractmethod
    def sheet_lines(self) -> list[str]:
        """The state as short lines for an export's sheet section."""

    def export_character(self) -> CharacterDetails | None:
        """The character an export names under the title, when the mode has one."""
        return None

    def record(self, entry: HistoryEntry) -> None:
        self.history.append(entry)

    def notice(self, message: str) -> str:
        self.record(HistoryEntry(notice=message))
        return message

    def roll_one_die(self) -> str:
        return self.notice(f"Rolled 1d6: {roll_d6(self.rng)}.")

    def has_unsaved_state(self) -> bool:
        """Whether anything would be lost by replacing this game.

        After a save or load, that is any change since; before one, anything at all.
        """
        if self.saved_snapshot is not None:
            return self.snapshot() != self.saved_snapshot
        return bool(self.history) or self.wrote_anything() or self.in_play

    def snapshot(self) -> dict[str, object]:
        """What a save keeps, apart from the file path, which only says where it goes."""
        return {"history": tuple(self.history), "name": self.name, "notes": self.notes}

    def wrote_anything(self) -> bool:
        """Whether the player typed anything: the session name or notes.

        The file path is left out: it is where a load reads from, so it would always count.
        """
        return bool(self.name or self.notes)

    def save(self, *, overwrite: bool = False) -> str:
        if not self.name.strip():
            raise ValueError("Name the session before saving.")
        with reported("save session"):
            path = session_file_path(self.path)
            saved = self.saved_session(self.name)
            saved.save(path, overwrite=overwrite)
        self.name = saved.name
        self.saved_snapshot = self.snapshot()
        return f"Saved {saved.name} to {path}."

    def read_save(self, text: str) -> tuple[BaseModel, Path]:
        """Read a session file without changing the game, so the player can confirm first."""
        with reported("load session"):
            path = session_file_path(text)
            contents = path.read_text(encoding="utf-8")
        return self.read_save_text(contents), path

    def read_save_text(self, text: str) -> BaseModel:
        """Read a save from its text, such as a file uploaded in the browser."""
        with reported("load session"):
            return self.parse_save(text)

    def load(self, saved: BaseModel, path: Path | None) -> str:
        """Take over ``saved``; ``path`` is the file it came from, None for an uploaded one."""
        self.take_over(saved)
        self.path = str(path) if path is not None else ""
        self.saved_snapshot = self.snapshot()
        return f"Loaded {saved.name} from {path}." if path is not None else f"Loaded {saved.name}."

    def save_text(self) -> str:
        """The game as a save file holds it, for the browser to download."""
        if not self.savable:
            raise ValueError("Start the game before downloading a save.")
        return self.saved_session(self.name.strip() or UNNAMED).model_dump_json(indent=2)

    def file_name(self) -> str:
        """The session file's name, or "" when no file is set (``..`` names none)."""
        name = Path(self.path.strip()).name
        return "" if name == ".." else name

    def save_file_name(self) -> str:
        """The session file's name, or one made from the session name, for a download."""
        return self.file_name() or f"{self.name.strip() or 'session'}.json"

    def take_over(self, saved: BaseModel) -> None:
        """Replace this game with ``saved``: the history, name and notes, with nothing to undo."""
        self.history = list(saved.history)
        self.name = saved.name
        self.notes = saved.notes
        self.undo_stack = []

    def start_over(self) -> None:
        """Clear what a new game does not keep: the history, name, file path, notes and Undo."""
        self.history.clear()
        self.name = self.path = self.notes = ""
        self.saved_snapshot = None
        self.undo_stack = []

    @contextmanager
    def undoable(self, change: str, *, options: bool = False) -> Iterator[None]:
        """Run a change to the state so Undo can take it back; a refused change adds nothing.

        ``options`` keeps the mode's options too, for a change that resets them.
        """
        state = self.state.model_copy(deep=True)
        kept = self.options() if options else None
        yield
        before = Before(change, state, self.typed_names(self.state), kept)
        self.undo_stack = [*self.undo_stack, before][-UNDO_LIMIT:]

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def undo(self) -> str:
        """Take back the last change to the state; the history keeps it and notes the undo.

        A roll taken back is not given back to the dice: rolling again gives new faces.
        """
        if not self.undo_stack:
            raise ValueError("There is nothing to undo.")
        before = self.undo_stack.pop()
        restored = self.typed_names(before.state)
        # A name belongs to the player, not to the change: one typed since it stays.
        kept = {
            slot: name
            for slot, name in self.typed_names(self.state).items()
            if slot in restored and name != before.names.get(slot)
        }
        action = f"Undid the last {before.change}"
        self.restore(before.state, kept, action)
        if before.options is not None:
            self.restore_options(before.options)
        return f"{action}."

    def keep_recovery(self) -> str:
        """Bring the recovery copy in step with the game, after any change.

        A game that cannot be saved yet leaves an earlier copy alone. A copy that cannot be
        written is reported once, and play goes on.
        """
        if self.recovery_path is None:
            return ""
        try:
            if not self.has_unsaved_state():
                if self.recovery_snapshot is not None:
                    self.discard_recovery()
            elif self.savable and self.snapshot() != self.recovery_snapshot:
                self.write_recovery()
        except (OSError, ValueError) as error:
            if self.recovery_failed:
                return ""
            self.recovery_failed = True
            return f"Could not keep a recovery copy: {player_message(error)}"
        return ""

    def write_recovery(self) -> None:
        # The stand-in is cut to what a save allows; ``name`` keeps the full text.
        stand_in = (self.name.strip() or UNNAMED)[:NAME_MAX]
        recovery = Recovery(name=self.name, path=self.path, game=self.saved_session(stand_in))
        self.recovery_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(self.recovery_path, recovery.model_dump_json(indent=2), overwrite=True)
        self.recovery_snapshot = self.snapshot()

    def discard_recovery(self) -> None:
        """Remove the recovery copy, as when the player chose to lose the unsaved changes."""
        # A copy that cannot be removed is only offered again on the next start.
        if self.recovery_path is not None:
            with suppress(OSError):
                self.recovery_path.unlink(missing_ok=True)
        self.recovery_snapshot = None

    def recovery_available(self) -> bool:
        """Whether a copy from an earlier run waits, and taking it would lose nothing here."""
        return (
            self.recovery_path is not None
            and self.recovery_path.is_file()
            and not self.has_unsaved_state()
        )

    def restore_recovery(self) -> str:
        """Take back the game an earlier run left unsaved; it stays unsaved until saved."""
        if self.recovery_path is None:
            raise ValueError("There is no recovery copy to restore.")
        with reported("restore the game"):
            text = self.recovery_path.read_text(encoding="utf-8")
            recovery = Recovery.read(text)
        self.take_over(recovery.game)
        self.name, self.path = recovery.name, recovery.path
        self.saved_snapshot = None
        # The copy already holds this game, so the next change need not write it again first.
        self.recovery_snapshot = self.snapshot()
        return "Restored the game wid had kept; save it to keep it for good."

    def open_file(self, text: str) -> str:
        """Load the save named on the command line; one that cannot be loaded says why instead."""
        try:
            saved, path = self.read_save(text)
        except ValueError as error:
            return str(error)
        return self.load(saved, path)

    def default_export_path(self) -> str:
        """The session file's path with a .md ending, or a plain name when none is set."""
        if not self.file_name():
            return "history.md"
        return str(Path(self.path.strip()).with_suffix(".md"))

    def require_history(self) -> None:
        if not self.history:
            raise ValueError("There is no history to export yet.")

    def history_text(self) -> str:
        """The history as the Markdown an export writes (or a browser downloads)."""
        self.require_history()
        return history_markdown(
            self.name,
            self.export_character(),
            self.history,
            sheet=self.sheet_lines(),
            notes=self.notes,
            statistics=history_statistics(self.history),
        )

    def export_history(self, text: str, *, overwrite: bool = False) -> str:
        markdown = self.history_text()
        with reported("export history"):
            path = session_file_path(text, label="history file")
            write_text(path, markdown, overwrite=overwrite)
        return f"Exported {len(self.history)} history entries to {path}."
