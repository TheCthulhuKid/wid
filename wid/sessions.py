import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from wid.history import HistoryEntry
from wid.profiles import Genre
from wid.rolls import FrozenModel, Index, RollRequest, RollSession


def session_file_path(value: str | Path) -> Path:
    value = str(value).strip()
    if not value:
        raise ValueError("Choose a session file path")
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
        session = self.session
        if session.attributes is None:
            raise ValueError("Start the game before saving a session")
        self.validate_request(self.draft)
        result = session.current_result
        if result is not None:
            self.validate_request(result.request)
            if result.strain_delta != result.request.power.cost:
                raise ValueError("Result strain must match its power")
            if result.strain_delta > session.total_strain:
                raise ValueError("Result strain exceeds session total")
            if result.corruption_delta > session.total_corruption:
                raise ValueError("Result Corruption exceeds session total")
            if result.corruption_delta > len(result.dice):
                raise ValueError("Invalid reroll Corruption cost")
        if session.total_strain and session.profile_id != Genre.HECKBOY:
            raise ValueError("Only Heckboy can have strain")
        if session.total_corruption and session.profile_id != Genre.OLDHEART:
            raise ValueError("Only Oldheart can have Corruption")
        self.validate_tech()
        if self.item_target is not None and (
            result is None or self.item_target >= len(result.dice)
        ):
            raise ValueError("Item target requires a valid die from the current result")
        if self.reroll_indices:
            if session.profile_id != Genre.OLDHEART or result is None:
                raise ValueError("Reroll selections require an Oldheart result")
            if any(index >= len(result.dice) for index in self.reroll_indices):
                raise ValueError("Reroll selection is outside the current result")
        return self

    def validate_request(self, request: RollRequest) -> None:
        if request.profile_id != self.session.profile_id:
            raise ValueError("Saved request must match the session genre")
        if request.attribute_rank != self.session.attribute_rank(request.attribute):
            raise ValueError("Saved request must use the assigned attribute rank")

    def validate_tech(self) -> None:
        tech = self.session.tech
        if tech is not None:
            if self.session.profile_id != Genre.SECOND_CONTACT:
                raise ValueError("Only Second Contact can have Tech")
            if (tech.science, tech.culture) != (
                self.session.attribute_rank("Science"),
                self.session.attribute_rank("Culture"),
            ):
                raise ValueError("Tech must use the assigned Science and Culture ranks")
            if tech.remaining_bonus > tech.science + tech.culture:
                raise ValueError("Tech strength exceeds its starting bonus")
        if self.draft.tech_target is not None and (tech is None or tech.remaining_bonus == 0):
            raise ValueError("Draft Tech target requires available Tech")

    def save(self, path: Path, *, overwrite: bool = False) -> None:
        candidate = SavedSession.model_validate(self.model_dump())
        path = session_file_path(path)
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(candidate.model_dump_json(indent=2))
                output.flush()
                os.chmod(temporary, self._target_mode(path))
                os.fsync(output.fileno())
            if overwrite:
                os.replace(temporary, path)
            else:
                self._publish_new(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _target_mode(path: Path) -> int:
        """Keep an existing save's permissions; otherwise honour the umask."""
        try:
            return stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            return 0o666 & ~umask

    @staticmethod
    def _publish_new(temporary: Path, path: Path) -> None:
        """Move a finished file into place without replacing an existing one."""
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise
        except OSError:
            # No hard links (e.g. FAT/exFAT): reserve the name exclusively, then
            # rename over the empty reservation so the path never holds a partial save.
            path.open("xb").close()
            try:
                os.replace(temporary, path)
            except BaseException:
                path.unlink(missing_ok=True)
                raise

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate_json(session_file_path(path).read_text(encoding="utf-8"))
