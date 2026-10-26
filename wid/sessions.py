from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from wid.history import HistoryEntry
from wid.profiles import Genre
from wid.rolls import FrozenModel, Index, RollRequest, RollSession, TechState
from wid.storage import write_text


def session_file_path(value: str | Path, *, label: str = "session file") -> Path:
    value = str(value).strip()
    if not value:
        raise ValueError(f"Choose a {label} path")
    try:
        return Path(value).expanduser()
    except RuntimeError as error:
        raise ValueError("Could not determine the path's home directory") from error


class CharacterDetails(FrozenModel):
    name: str = ""
    looks: str = ""
    nature: str = ""


class SavedSession(FrozenModel):
    version: Literal[1] = 1
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    session: RollSession
    draft: RollRequest
    notes: str = ""
    character: CharacterDetails = Field(default_factory=CharacterDetails)
    history: tuple[HistoryEntry, ...] = ()
    reroll_indices: tuple[Index, ...] = ()
    item_target: Index | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.session.attributes is None:
            raise ValueError("Start the game before saving a session")
        self.validate_request(self.draft)
        self.validate_result()
        self.validate_resources()
        self.validate_tech()
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

    def validate_tech(self) -> None:
        tech = self.session.tech
        piece = self.draft.tech_piece
        if tech is None:
            if piece is not None:
                raise ValueError("Draft Tech target requires available Tech")
            return
        self.validate_tech_slots(tech)
        if piece is not None and tech.piece(piece).strength == 0:
            raise ValueError("Draft Tech target requires available Tech")

    def validate_tech_slots(self, tech: TechState) -> None:
        session = self.session
        if session.profile_id != Genre.SECOND_CONTACT:
            raise ValueError("Only Second Contact can have Tech")
        ranks = (session.attribute_rank("Science"), session.attribute_rank("Culture"))
        if (tech.science, tech.culture) != ranks:
            raise ValueError("Tech must use the assigned Science and Culture ranks")
        if len(tech.pieces) != session.attribute_rank("Muscle"):
            raise ValueError("Tech needs one slot per Muscle rank")

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
        candidate = SavedSession.model_validate(self.model_dump())
        write_text(
            session_file_path(path), candidate.model_dump_json(indent=2), overwrite=overwrite
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate_json(session_file_path(path).read_text(encoding="utf-8"))
