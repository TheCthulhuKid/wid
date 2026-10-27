"""One sitting at the table: the state every front end drives, and the messages it reports.

Each action changes the game and returns the feedback to show (empty when there is nothing to
say); refused actions raise ``ValueError`` with a message for the player. History entries are
appended here, so front ends only display ``Game.history``. Saving and exporting raise
``FileExistsError`` (with the target in ``filename``) when they would replace a file, so the
front end can ask before calling again with ``overwrite=True``.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from random import Random
from typing import Any, Literal, NamedTuple

from pydantic import ValidationError

from wid.export import history_markdown
from wid.formatting import (
    BONUS_LABELS,
    check_summary,
    resources_notice,
    spend_summary,
    standing_notice,
    strain_notice,
)
from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre, WiDProfile
from wid.rolls import (
    SCARED_MAX,
    BonusKind,
    PowerMode,
    ResourceEffect,
    RollRequest,
    RollResult,
    RollSession,
    roll_d6,
)
from wid.sessions import CharacterDetails, Recovery, SavedSession, session_file_path
from wid.storage import write_text

type NameField = Literal["bonus", "power", "manifestation", "tech", "strain"]

# The session setter for each name the player types; the slot is the bonus kind for bonuses
# and the row or index for the others.
RENAMERS: dict[NameField, Callable[[RollSession, Any, str], object]] = {
    "bonus": RollSession.set_bonus_name,
    "power": RollSession.set_power_name,
    "manifestation": RollSession.set_manifestation_name,
    "tech": RollSession.set_tech_name,
    "strain": RollSession.set_strain_name,
}


def player_message(error: Exception) -> str:
    """The reason to show the player: pydantic's first message, without its prefix."""
    if isinstance(error, ValidationError):
        return error.errors()[0]["msg"].removeprefix("Value error, ")
    # An OS error reads "No such file or directory: game.json", without Python's "[Errno 2]".
    if isinstance(error, OSError) and error.strerror:
        return f"{error.strerror}: {error.filename}" if error.filename else error.strerror
    return str(error)


# A save needs a name; the recovery copy of a game that has none uses this one.
UNNAMED = "Unsaved game"
# How many changes Undo can take back.
UNDO_LIMIT = 50


class Before(NamedTuple):
    """The game just before a change, and the change's name for "Undid the last ..."."""

    change: str
    session: RollSession
    # What the change may have reset: the tested attribute, the one-test options and the picks.
    options: tuple[Any, ...]


class Game:
    def __init__(self, *, rng: Random | None = None, recovery_path: Path | None = None):
        self.rng = rng if rng is not None else Random()
        self.history: list[HistoryEntry] = []
        self.name = ""
        self.path = ""
        self.notes = ""
        # What the last save or load held, to tell whether anything has changed since.
        self.saved_snapshot: dict[str, object] | None = None
        # Where unsaved changes are kept in case wid closes; None keeps no copy (as in tests).
        self.recovery_path = recovery_path
        # What this run last wrote there, so an unchanged game is not written again.
        self.recovery_snapshot: dict[str, object] | None = None
        self.recovery_failed = False
        self.reset_sheet(Genre.CORE)

    def reset_sheet(self, genre: Genre) -> None:
        """A fresh character of ``genre``: session, details and the options for the next test."""
        self.session = RollSession(profile_id=genre)
        self.character = CharacterDetails()
        self.tested_attribute = PROFILES[genre].attributes[0]
        self.fear_level = 0
        self.assisted = False
        self.expertise = False
        self.power = PowerMode.NONE
        # Choices about the current result, kept so a save can restore them.
        self.reroll_selection: tuple[int, ...] = ()
        self.item_target: int | None = None
        # A new sheet has nothing to take back.
        self.undo_stack: list[Before] = []

    @property
    def profile(self) -> WiDProfile:
        return PROFILES[self.session.profile_id]

    def record(self, entry: HistoryEntry) -> None:
        self.history.append(entry)

    def notice(self, message: str) -> str:
        self.record(HistoryEntry(notice=message))
        return message

    def log_result(self, result: RollResult, action: str, *, charged: bool = True) -> None:
        session = self.session
        self.record(
            HistoryEntry(
                action=action,
                result=result,
                charged=charged,
                total_strain=session.total_strain,
                total_corruption=session.total_corruption,
                tech_pieces=session.tech.pieces if session.tech else None,
                expertise_name=session.bonuses.expertise,
            )
        )
        self.reroll_selection = ()
        # A new roll can have fewer dice than the one the item was aimed at.
        if self.item_target is not None and self.item_target >= self.dice_count:
            self.item_target = None

    @property
    def dice_count(self) -> int:
        result = self.session.current_result
        return len(result.dice) if result is not None else 0

    def set_test_options(
        self,
        *,
        fear_level: int,
        assisted: bool,
        expertise: bool,
        power: PowerMode,
        reroll: Iterable[int],
        item_target: int | None,
    ) -> None:
        """Take the options for the next test and the dice picked from the current result.

        Scared off its track is refused. A die the current result does not have is dropped, since
        a front end may still show the dice of an earlier roll, and so are rerolls in a kit
        without them.
        """
        if not 0 <= fear_level <= SCARED_MAX:
            raise ValueError(f"Scared runs from 0 to {SCARED_MAX}")
        count = self.dice_count
        self.fear_level = fear_level
        self.assisted = assisted
        self.expertise = expertise
        self.power = power
        picked = {index for index in reroll if 0 <= index < count}
        self.reroll_selection = tuple(sorted(picked)) if self.profile.has_rerolls else ()
        on_a_die = item_target is not None and 0 <= item_target < count
        self.item_target = item_target if on_a_die else None

    def rename(self, field: NameField, slot: int | BonusKind, name: str) -> None:
        """Name a bonus, power, manifestation, Tech piece or strain row; nothing is logged."""
        RENAMERS[field](self.session, slot, name)

    def draft_request(self, *, preview: bool = False) -> RollRequest:
        """The next test as the options stand; ``preview`` skips the rank, which needs setup."""
        session = self.session
        return RollRequest(
            profile_id=session.profile_id,
            attribute=self.tested_attribute,
            attribute_rank=1 if preview else session.attribute_rank(self.tested_attribute),
            assisted=self.assisted,
            fear_level=self.fear_level,
            expertise=self.expertise,
            power=self.power if self.profile.has_powers else PowerMode.NONE,
            resource_die=session.resource_die,
            manifestations=len(session.manifestations),
        )

    def start_game(self, ranks: tuple[int, ...]) -> str:
        self.session.configure_attributes(ranks)
        return "Attributes set for this game; press Roll beside an attribute."

    def roll(self, attribute: str | None = None) -> str:
        """Test ``attribute``, or the last tested one again; one-test options are then cleared."""
        with self.undoable("roll"):
            if attribute is not None:
                self.session.attribute_rank(attribute)
                self.tested_attribute = attribute
            result = self.session.roll(self.draft_request(), rng=self.rng)
            self.log_result(result, "Roll")
            self.assisted = self.expertise = False
            self.power = PowerMode.NONE
        return ""

    def reroll(self, indices: set[int]) -> str:
        with self.undoable("reroll"):
            result = self.session.reroll(indices, rng=self.rng)
            self.log_result(result, f"Reroll dice {', '.join(str(i + 1) for i in sorted(indices))}")
        return check_summary(result.manifestation_check)

    def apply_bonus(self, kind: BonusKind, die: int) -> str:
        """Expertise adds a hit; an item adds 1 to ``die``."""
        name = getattr(self.session.bonuses, kind)
        with self.undoable("bonus"):
            if kind == BonusKind.EXPERTISE:
                result = self.session.apply_expertise()
                action = f"Expertise {name}: +1 hit"
            else:
                result = self.session.apply_item(kind, die)
                action = f"{BONUS_LABELS[kind]} {name}: +1 to die {die + 1}"
            self.log_result(result, action, charged=False)
        return ""

    def bonus_available(self, kind: BonusKind) -> bool:
        """Whether the bonus is named and still unused on the current test."""
        session = self.session
        result = session.current_result
        if result is None or not getattr(session.bonuses, kind).strip():
            return False
        if kind == BonusKind.EXPERTISE:
            return not result.request.expertise
        if kind == BonusKind.CRAFTED_ITEM and not session.item_crafted:
            return False
        return kind not in result.applied_items

    def apply_tech(self, index: int, die: int) -> str:
        with self.undoable("Tech use"):
            result = self.session.apply_tech(index, die)
            piece = self.session.tech.pieces[index]
            # Using a piece weakens it by 1, so the bonus it gave was one more than it has left.
            action = f"Tech {piece.label(index)}: +{piece.strength + 1} to die {die + 1}"
            self.log_result(result, action, charged=False)
        return ""

    def tech_usable(self, index: int) -> bool:
        """Whether Tech slot ``index`` holds a named, working piece unused on the current test."""
        result = self.session.current_result
        return (
            self.session.tech.pieces[index].working
            and result is not None
            and index not in result.applied_tech
        )

    def set_strain_box(self, index: int, marked: bool) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.set_box(index, marked)
        change = "Marked" if marked else "Cleared"
        return self.notice(strain_notice(f"{change} strain box {index + 1}", self.session.strain))

    def take_strain(self) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.take_by_hand()
        return self.notice(strain_notice("Took 1 strain", self.session.strain))

    def take_wound(self) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.take_wound()
        return self.notice(strain_notice("Took a wound", self.session.strain))

    def start_scenario(self) -> str:
        with self.undoable("new scenario"):
            tech = self.session.start_scenario()
        return self.notice(f"New scenario: {len(tech.pieces)} empty Tech slot(s).")

    def sacrifice_tech(self, index: int) -> str:
        with self.undoable("sacrifice"):
            piece = self.session.sacrifice_tech(index)
        return self.notice(f"Sacrificed {piece.label(index)}: strength {piece.strength} → 0.")

    def adjust_resources(self, amount: int) -> str:
        with self.undoable("Resources change"):
            pool = self.session.adjust_resources(amount)
        return self.notice(resources_notice(amount, pool))

    def spend_resources(self, effect: ResourceEffect) -> str:
        with self.undoable("Resources spend"):
            spend = self.session.spend_resources(effect, rng=self.rng)
        return self.notice(spend_summary(spend, self.session.resources))

    def lose_crafted_item(self) -> str:
        with self.undoable("lost crafted item"):
            self.session.lose_crafted_item()
        return self.notice("Lost the crafted item; its slot is free again.")

    def gain_corruption(self, amount: int) -> str:
        with self.undoable("Corruption gain"):
            check = self.session.add_corruption(amount, rng=self.rng)
        return self.notice(f"Gained {amount} Corruption. {check_summary(check)}")

    def add_manifestation(self) -> str:
        with self.undoable("manifestation change"):
            self.session.add_manifestation()
        return self.notice("Manifestation added by hand.")

    def remove_manifestation(self) -> str:
        with self.undoable("manifestation change"):
            self.session.remove_manifestation()
        return self.notice("Manifestation removed by hand.")

    def set_standing(self, standing: int) -> str:
        # Clicking the dot already chosen moves nothing, so there is nothing to log or undo.
        if standing == self.session.standing:
            return ""
        with self.undoable("Standing change"):
            standing = self.session.set_standing(standing)
        return self.notice(standing_notice(standing))

    def roll_one_die(self) -> str:
        return self.notice(f"Rolled 1d6: {roll_d6(self.rng)}.")

    def new_character(self) -> str:
        """Start the sheet over in the same kit; history, notes and the file stay."""
        self.reset_sheet(self.session.profile_id)
        return self.notice("New character started.")

    def change_kit(self, genre: Genre) -> str:
        """A genre kit lasts a whole game, so changing it starts over: sheet, history and file."""
        self.reset_sheet(genre)
        self.history.clear()
        self.name = self.path = self.notes = ""
        self.saved_snapshot = None
        return f"New {PROFILES[genre].name} game started."

    def has_unsaved_state(self) -> bool:
        """Whether anything would be lost by replacing this game.

        After a save or load, that is any change since; before one, anything at all.
        """
        if self.saved_snapshot is not None:
            return self.snapshot() != self.saved_snapshot
        return bool(self.history) or self.wrote_anything() or self.session.in_play

    def snapshot(self) -> dict[str, object]:
        """What a save keeps, apart from the file path, which only says where it goes.

        The dice picked for a reroll or an item are left out: they are not worth a question.
        """
        return {
            "session": self.session.model_dump(),
            "history": tuple(self.history),
            "name": self.name,
            "notes": self.notes,
            "character": self.character,
            "draft": (
                self.tested_attribute,
                self.fear_level,
                self.assisted,
                self.expertise,
                self.power,
            ),
        }

    def wrote_anything(self) -> bool:
        """Whether the player typed anything: the session name, notes, details or names.

        The file path is left out: it is where a load reads from, so it would always count.
        """
        session = self.session
        written = (
            self.name,
            self.notes,
            *self.character.model_dump().values(),
            *session.bonuses.model_dump().values(),
            *session.power_names,
            *session.strain.names,
        )
        return any(written)

    def save(self, *, overwrite: bool = False) -> str:
        if not self.name.strip():
            raise ValueError("Name the session before saving.")
        try:
            path = session_file_path(self.path)
            saved = self.saved_session(self.name)
            saved.save(path, overwrite=overwrite)
        except FileExistsError:
            raise
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not save session: {player_message(error)}") from error
        self.name = saved.name
        self.saved_snapshot = self.snapshot()
        return f"Saved {saved.name} to {path}."

    def saved_session(self, name: str) -> SavedSession:
        """The game as a save file holds it, under ``name``."""
        return SavedSession(
            name=name,
            session=self.session.model_copy(deep=True),
            draft=self.draft_request(),
            notes=self.notes,
            character=self.character,
            history=tuple(self.history),
            reroll_indices=self.reroll_selection,
            item_target=self.item_target,
        )

    def read_save(self, text: str) -> tuple[SavedSession, Path]:
        """Read a session file without changing the game, so the player can confirm first."""
        try:
            path = session_file_path(text)
            return SavedSession.load(path), path
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not load session: {player_message(error)}") from error

    def load(self, saved: SavedSession, path: Path) -> str:
        self.take_over(saved)
        self.path = str(path)
        self.saved_snapshot = self.snapshot()
        return f"Loaded {saved.name} from {path}."

    def take_over(self, saved: SavedSession) -> None:
        """Replace this game with ``saved``: the sheet, history, name, notes and options."""
        self.session = saved.session.model_copy(deep=True)
        self.history = list(saved.history)
        self.name = saved.name
        self.notes = saved.notes
        self.character = saved.character
        draft = saved.draft
        self.tested_attribute = draft.attribute
        self.fear_level = draft.fear_level
        self.assisted = draft.assisted
        self.expertise = draft.expertise
        self.power = draft.power
        self.reroll_selection = saved.reroll_indices
        self.item_target = saved.item_target
        self.undo_stack = []

    def options(self) -> tuple[Any, ...]:
        return (
            self.tested_attribute,
            self.assisted,
            self.expertise,
            self.power,
            self.reroll_selection,
            self.item_target,
        )

    @contextmanager
    def undoable(self, change: str) -> Iterator[None]:
        """Run a change to the sheet so Undo can take it back; a refused change adds nothing."""
        before = Before(change, self.session.model_copy(deep=True), self.options())
        yield
        self.undo_stack = [*self.undo_stack, before][-UNDO_LIMIT:]

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def undo(self) -> str:
        """Take back the last change to the sheet; the history keeps it and notes the undo.

        A roll taken back is not given back to the dice: rolling again gives new faces.
        """
        if not self.undo_stack:
            raise ValueError("There is nothing to undo.")
        before = self.undo_stack.pop()
        shown = self.session.current_result
        self.session = before.session
        message = f"Undid the last {before.change}."
        result = self.session.current_result
        # When the dice change back, the history shows them as they are again.
        if result is not None and result != shown:
            self.log_result(result, message, charged=False)
        else:
            self.notice(message)
        (
            self.tested_attribute,
            self.assisted,
            self.expertise,
            self.power,
            self.reroll_selection,
            self.item_target,
        ) = before.options
        return message

    def keep_recovery(self) -> str:
        """Bring the recovery copy in step with the game, after any change.

        While something is unsaved the copy holds the game; once nothing is (after a save, a
        load or a new kit), the copy this run wrote goes. Before the game starts there is no
        sheet to save, so an earlier copy is left alone. A copy that cannot be written is
        reported once, as a message to show, and play carries on.
        """
        if self.recovery_path is None:
            return ""
        try:
            if not self.has_unsaved_state():
                if self.recovery_snapshot is not None:
                    self.discard_recovery()
            elif self.session.attributes is not None and self.snapshot() != self.recovery_snapshot:
                self.write_recovery()
        except (OSError, ValueError) as error:
            if self.recovery_failed:
                return ""
            self.recovery_failed = True
            return f"Could not keep a recovery copy: {player_message(error)}"
        return ""

    def write_recovery(self) -> None:
        recovery = Recovery(
            name=self.name, path=self.path, game=self.saved_session(self.name.strip() or UNNAMED)
        )
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
        try:
            text = self.recovery_path.read_text(encoding="utf-8")
            recovery = Recovery.model_validate_json(text)
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not restore the game: {player_message(error)}") from error
        self.take_over(recovery.game)
        self.name, self.path = recovery.name, recovery.path
        self.saved_snapshot = None
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
        path = Path(self.path.strip())
        if not path.name or path.name == "..":
            return "history.md"
        return str(path.with_suffix(".md"))

    def require_history(self) -> None:
        if not self.history:
            raise ValueError("There is no history to export yet.")

    def history_text(self) -> str:
        """The history as the Markdown an export writes (or a browser downloads)."""
        self.require_history()
        return history_markdown(self.name, self.character, self.history)

    def export_history(self, text: str, *, overwrite: bool = False) -> str:
        markdown = self.history_text()
        try:
            path = session_file_path(text, label="history file")
            write_text(path, markdown, overwrite=overwrite)
        except FileExistsError:
            raise
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not export history: {player_message(error)}") from error
        return f"Exported {len(self.history)} history entries to {path}."
