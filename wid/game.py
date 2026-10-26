"""One sitting at the table: the state every front end drives, and the messages it reports.

Each action changes the game and returns the feedback to show (empty when there is nothing to
say); refused actions raise ``ValueError`` with a message for the player. History entries are
appended here, so front ends only display ``Game.history``. Saving and exporting raise
``FileExistsError`` (with the target in ``filename``) when they would replace a file, so the
front end can ask before calling again with ``overwrite=True``.
"""

import errno
from pathlib import Path
from random import Random

from wid.export import history_markdown
from wid.formatting import BONUS_LABELS, check_summary, spend_summary
from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre, WiDProfile
from wid.rolls import (
    STANDING_START,
    BonusKind,
    PowerMode,
    ResourceEffect,
    RollRequest,
    RollResult,
    RollSession,
    roll_d6,
)
from wid.sessions import CharacterDetails, SavedSession, session_file_path
from wid.storage import write_text


def file_exists(path: Path) -> FileExistsError:
    """The error naming ``path``: the one from storage names its temporary file instead."""
    return FileExistsError(errno.EEXIST, "File exists", str(path))


class Game:
    def __init__(self, *, rng: Random | None = None):
        self.rng = rng if rng is not None else Random()
        self.history: list[HistoryEntry] = []
        self.name = ""
        self.path = ""
        self.notes = ""
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
        if attribute is not None:
            self.session.attribute_rank(attribute)
            self.tested_attribute = attribute
        result = self.session.roll(self.draft_request(), rng=self.rng)
        self.log_result(result, "Roll")
        self.assisted = self.expertise = False
        self.power = PowerMode.NONE
        return ""

    def reroll(self, indices: set[int]) -> str:
        result = self.session.reroll(indices, rng=self.rng)
        self.log_result(result, f"Reroll dice {', '.join(str(i + 1) for i in sorted(indices))}")
        return check_summary(result.manifestation_check)

    def apply_bonus(self, kind: BonusKind, die: int) -> str:
        """Expertise adds a hit; an item adds 1 to ``die``."""
        name = getattr(self.session.bonuses, kind)
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
        result = self.session.apply_tech(index, die)
        piece = self.session.tech.pieces[index]
        # Using a piece weakens it by 1, so the bonus it just gave was one more than it has left.
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

    def undo_bonus(self) -> str:
        result = self.session.undo_bonus()
        self.log_result(result, "Undo last bonus", charged=False)
        return ""

    def set_strain_box(self, index: int, marked: bool) -> str:
        self.session.strain = self.session.strain.set_box(index, marked)
        return ""

    def take_strain(self) -> str:
        self.session.strain = self.session.strain.take(1)
        return ""

    def take_wound(self) -> str:
        self.session.strain = self.session.strain.take_wound()
        return ""

    def start_scenario(self) -> str:
        tech = self.session.start_scenario()
        return self.notice(f"New scenario: {len(tech.pieces)} empty Tech slot(s).")

    def sacrifice_tech(self, index: int) -> str:
        piece = self.session.sacrifice_tech(index)
        return self.notice(f"Sacrificed {piece.label(index)}: strength {piece.strength} → 0.")

    def adjust_resources(self, amount: int) -> str:
        self.session.adjust_resources(amount)
        return ""

    def spend_resources(self, effect: ResourceEffect) -> str:
        spend = self.session.spend_resources(effect, rng=self.rng)
        return self.notice(spend_summary(spend, self.session.resources))

    def lose_crafted_item(self) -> str:
        self.session.lose_crafted_item()
        return self.notice("Lost the crafted item; its slot is free again.")

    def gain_corruption(self, amount: int) -> str:
        check = self.session.add_corruption(amount, rng=self.rng)
        return self.notice(f"Gained {amount} Corruption. {check_summary(check)}")

    def add_manifestation(self) -> str:
        self.session.add_manifestation()
        return self.notice("Manifestation added by hand.")

    def remove_manifestation(self) -> str:
        self.session.remove_manifestation()
        return self.notice("Manifestation removed by hand.")

    def set_standing(self, standing: int) -> str:
        self.session.set_standing(standing)
        return ""

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
        return f"New {PROFILES[genre].name} game started."

    def has_unsaved_state(self) -> bool:
        """Whether anything would be lost by replacing this game."""
        session = self.session
        return bool(
            session.attributes is not None
            or self.history
            or self.notes
            or any(self.character.model_dump().values())
            or any(session.bonuses.model_dump().values())
            or any(session.power_names)
            or session.standing != STANDING_START
            or session.total_strain
            or session.total_corruption
            or any(session.strain.boxes)
            or any(session.strain.names)
            or session.manifestations
        )

    def save(self, *, overwrite: bool = False) -> str:
        session = self.session
        try:
            path = session_file_path(self.path)
            saved = SavedSession(
                name=self.name,
                session=session.model_copy(deep=True),
                draft=self.draft_request(),
                notes=self.notes,
                character=self.character,
                history=tuple(self.history),
                reroll_indices=tuple(sorted(self.reroll_selection)),
                item_target=self.item_target if session.current_result is not None else None,
            )
            saved.save(path, overwrite=overwrite)
        except FileExistsError as error:
            raise file_exists(path) from error
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not save session: {error}") from error
        self.name = saved.name
        return f"Saved {saved.name} to {path}."

    def read_save(self, text: str) -> tuple[SavedSession, Path]:
        """Read a session file without changing the game, so the player can confirm first."""
        try:
            path = session_file_path(text)
            return SavedSession.load(path), path
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not load session: {error}") from error

    def load(self, saved: SavedSession, path: Path) -> str:
        self.session = saved.session.model_copy(deep=True)
        self.history = list(saved.history)
        self.name = saved.name
        self.path = str(path)
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
        return f"Loaded {saved.name} from {path}."

    def default_export_path(self) -> str:
        """The session file's path with a .md ending, or a plain name when none is set."""
        path = Path(self.path.strip())
        if not path.name or path.name == "..":
            return "history.md"
        return str(path.with_suffix(".md"))

    def require_history(self) -> None:
        if not self.history:
            raise ValueError("There is no history to export yet.")

    def export_history(self, text: str, *, overwrite: bool = False) -> str:
        self.require_history()
        try:
            path = session_file_path(text, label="history file")
            markdown = history_markdown(self.name, self.character, self.history)
            write_text(path, markdown, overwrite=overwrite)
        except FileExistsError as error:
            raise file_exists(path) from error
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not export history: {error}") from error
        return f"Exported {len(self.history)} history entries to {path}."
