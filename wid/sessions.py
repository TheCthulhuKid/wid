from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import STANDING_START, FrozenModel, Index, RollRequest, RollSession
from wid.storage import write_text


def session_file_path(value: str | Path, *, label: str = "session file") -> Path:
    value = str(value).strip()
    if not value:
        raise ValueError(f"Choose a {label} path")
    try:
        path = Path(value).expanduser()
    except RuntimeError as error:
        raise ValueError("Could not determine the path's home directory") from error
    # Checked first, so a folder is never offered as a file to replace.
    if path.is_dir():
        raise ValueError("That path is a folder; add a file name.")
    return path


class CharacterDetails(FrozenModel):
    name: str = ""
    looks: str = ""
    nature: str = ""


SaveData = dict[str, Any]


def note_succumbed_checks(data: SaveData) -> SaveData:
    """Version 2 notes on each manifestation check whether the character had already succumbed.

    Version 1 checks have no note, and its default (not succumbed) is how they were worded then.
    """
    return data


# Each function turns a save file of the version it is keyed by into the next version's data.
# A change to the save format bumps ``SavedSession.version`` and adds one function here.
UPGRADES: dict[int, Callable[[SaveData], SaveData]] = {1: note_succumbed_checks}


def upgrade_step(step: Callable[[SaveData], SaveData], data: SaveData, version: int) -> SaveData:
    """Run one upgrade; a file it cannot handle is refused rather than crashing a front end."""
    try:
        return step(data)
    except Exception as error:
        raise ValueError(f"This file could not be upgraded from save format {version}.") from error


# The longest session name a save holds.
NAME_MAX = 100
SessionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]


class SavedSession(FrozenModel):
    version: Literal[2] = 2
    name: SessionName
    session: RollSession
    draft: RollRequest
    notes: str = ""
    character: CharacterDetails = Field(default_factory=CharacterDetails)
    history: tuple[HistoryEntry, ...] = ()
    reroll_indices: tuple[Index, ...] = ()
    item_target: Index | None = None

    @model_validator(mode="before")
    @classmethod
    def upgrade(cls, data: Any) -> Any:
        """Bring an older save file up to the current version, one step at a time.

        A file from a newer wid, or with a version no wid wrote, is refused with a message that
        says so, instead of pydantic's "Input should be 2".
        """
        if not isinstance(data, dict):
            return data
        current = cls.model_fields["version"].default
        version = data.get("version", current)
        # Python counts true as 1, and JSON can hold 1.0; wid never writes either.
        if type(version) is int:
            while (step := UPGRADES.get(version)) is not None:
                data = {**upgrade_step(step, data, version), "version": version + 1}
                version += 1
            if version == current:
                return data
            if version > current:
                raise ValueError("This file was saved by a newer wid. Update wid to load it.")
        raise ValueError(f"This file has an unknown save format version ({version!r}).")

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.session.attributes is None:
            raise ValueError("Start the game before saving a session")
        self.validate_request(self.draft)
        self.validate_result()
        self.validate_resources()
        self.validate_tech()
        self.validate_pool_of_resources()
        self.validate_item_target()
        self.validate_reroll_indices()
        return self

    def validate_request(self, request: RollRequest) -> None:
        if request.profile_id != self.session.profile_id:
            raise ValueError("Saved request must match the session genre")
        if request.attribute_rank != self.session.attribute_rank(request.attribute):
            raise ValueError("Saved request must use the assigned attribute rank")

    def validate_result(self) -> None:
        session = self.session
        result = session.current_result
        if result is None:
            return
        self.validate_request(result.request)
        if result.strain_delta != result.request.power.cost:
            raise ValueError("Result strain must match its power")
        if result.strain_delta > session.total_strain:
            raise ValueError("Result strain exceeds session total")
        if result.corruption_delta > session.total_corruption:
            raise ValueError("Result Corruption exceeds session total")
        if result.corruption_delta > len(result.dice):
            raise ValueError("Invalid reroll Corruption cost")

    def validate_resources(self) -> None:
        session = self.session
        if session.total_strain and session.profile_id != Genre.HECKBOY:
            raise ValueError("Only Heckboy can have strain")
        if session.total_corruption and session.profile_id != Genre.OLDHEART:
            raise ValueError("Only Oldheart can have Corruption")
        if session.manifestations and session.profile_id != Genre.OLDHEART:
            raise ValueError("Only Oldheart can have manifestations")
        if self.draft.manifestations != len(session.manifestations):
            raise ValueError("Draft manifestations must match the character's")
        if session.standing != STANDING_START and not PROFILES[session.profile_id].has_standing:
            raise ValueError("Only Ball Season can have Standing")

    def validate_pool_of_resources(self) -> None:
        session = self.session
        if not PROFILES[session.profile_id].has_resources:
            if session.resources is not None or session.resource_die or session.item_crafted:
                raise ValueError("Only This Isn't Happening can have Resources")
            return
        if session.resources is None:
            raise ValueError("This Isn't Happening needs its Resources pool")
        if self.draft.resource_die and not session.resource_die:
            raise ValueError("Draft Resources die requires a waiting die")

    def validate_tech(self) -> None:
        session = self.session
        tech = session.tech
        result = session.current_result
        used = result.applied_tech if result is not None else frozenset()
        if session.profile_id != Genre.SECOND_CONTACT:
            if tech is not None or used:
                raise ValueError("Only Second Contact can have Tech")
            return
        if tech is None:
            raise ValueError("Second Contact needs its Tech slots")
        ranks = (session.attribute_rank("Science"), session.attribute_rank("Culture"))
        if (tech.science, tech.culture) != ranks:
            raise ValueError("Tech must use the assigned Science and Culture ranks")
        if len(tech.pieces) != session.attribute_rank("Muscle"):
            raise ValueError("Tech needs one slot per Muscle rank")
        if any(index >= len(tech.pieces) for index in used):
            raise ValueError("Used Tech is outside the Tech slots")

    def validate_item_target(self) -> None:
        if self.item_target is None:
            return
        result = self.session.current_result
        if result is None or self.item_target >= len(result.dice):
            raise ValueError("Item target requires a valid die from the current result")

    def validate_reroll_indices(self) -> None:
        if not self.reroll_indices:
            return
        result = self.session.current_result
        if self.session.profile_id != Genre.OLDHEART or result is None:
            raise ValueError("Reroll selections require an Oldheart result")
        if any(index >= len(result.dice) for index in self.reroll_indices):
            raise ValueError("Reroll selection is outside the current result")

    def save(self, path: Path, *, overwrite: bool = False) -> None:
        write_text(path, self.model_dump_json(indent=2), overwrite=overwrite)


class Recovery(FrozenModel):
    """The game as wid last changed it, kept until it is saved, so a crash loses nothing.

    A save needs a name, so ``game`` may carry a stand-in; ``name`` is the one the player typed,
    and ``path`` is the session file the game would be saved to.
    """

    name: str = ""
    path: str = ""
    game: SavedSession
