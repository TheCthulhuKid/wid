from enum import StrEnum
from random import Random
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictBool,
    TypeAdapter,
    model_validator,
)

from wid.profiles import PROFILES, Genre


class PowerMode(StrEnum):
    NONE = "none"
    RELIABLE = "reliable"
    ERRATIC = "erratic"

    @property
    def cost(self) -> int:
        return {PowerMode.NONE: 0, PowerMode.RELIABLE: 1, PowerMode.ERRATIC: 2}[self]


class Outcome(StrEnum):
    HIT = "hit"
    MISS = "miss"
    FUMBLE = "fumble"


class BonusKind(StrEnum):
    EXPERTISE = "expertise"
    APPROPRIATE_ITEM = "appropriate_item"
    INAPPROPRIATE_ITEM = "inappropriate_item"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NamedBonuses(FrozenModel):
    expertise: str = ""
    appropriate_item: str = ""
    inappropriate_item: str = ""


Index = Annotated[int, Field(strict=True, ge=0)]
Rank = Annotated[int, Field(strict=True, ge=1, le=3)]


class RollRequest(FrozenModel):
    profile_id: Genre = Genre.CORE
    assisted: bool = False
    fear_level: Annotated[int, Field(strict=True, ge=0, le=3)] = 0
    attribute_rank: Rank = 1
    attribute: str = "Athleticism"
    expertise: bool = False
    power: PowerMode = PowerMode.NONE
    tech_target: Index | None = None

    def pool_size(self) -> int:
        return 4 - self.fear_level + int(self.assisted) + self.power.cost

    @property
    def hit_threshold(self) -> int:
        return 4 if self.assisted else 5

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        self.validate_power()
        self.validate_tech_target()
        return self

    def validate_power(self) -> None:
        if self.power != PowerMode.NONE and self.profile_id != Genre.HECKBOY:
            raise ValueError("Only Heckboy can use powers")

    def validate_tech_target(self) -> None:
        if self.tech_target is None:
            return
        if self.profile_id != Genre.SECOND_CONTACT:
            raise ValueError("Only Second Contact can use Tech")
        if self.tech_target >= self.pool_size():
            raise ValueError("Tech target is outside the dice pool")


class DieResult(FrozenModel):
    raw: Annotated[int, Field(strict=True, ge=1, le=6)]
    bonus: Annotated[int, Field(strict=True, ge=0)] = 0

    @property
    def effective(self) -> int:
        return self.raw + self.bonus

    def classify(self, request: RollRequest) -> Outcome:
        if self.effective >= request.hit_threshold:
            return Outcome.HIT
        if self.effective <= request.attribute_rank:
            return Outcome.FUMBLE
        return Outcome.MISS


class RollTotals(FrozenModel):
    dice_hits: int
    expertise_hits: int
    misses: int
    fumbles: int

    @property
    def hits(self) -> int:
        return self.dice_hits + self.expertise_hits


class RollResult(FrozenModel):
    request: RollRequest
    dice: tuple[DieResult, ...]
    strain_delta: Annotated[int, Field(ge=0)] = 0
    corruption_delta: Annotated[int, Field(ge=0)] = 0
    # Each item adds +1 to one die per test, so an item used here cannot be used again.
    applied_items: frozenset[BonusKind] = frozenset()

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        if len(self.dice) != self.request.pool_size():
            raise ValueError("Result must contain the complete dice pool")
        return self

    def totals(self) -> RollTotals:
        outcomes = [die.classify(self.request) for die in self.dice]
        return RollTotals(
            dice_hits=outcomes.count(Outcome.HIT),
            expertise_hits=int(self.request.expertise),
            misses=outcomes.count(Outcome.MISS),
            fumbles=outcomes.count(Outcome.FUMBLE),
        )


class TechState(FrozenModel):
    science: Rank
    culture: Rank
    remaining_bonus: Annotated[int, Field(strict=True, ge=0)] = 0


class AttributeSetup(FrozenModel):
    profile_id: Genre
    ranks: tuple[Rank, ...]

    @model_validator(mode="after")
    def validate_ranks(self) -> Self:
        if len(self.ranks) != len(PROFILES[self.profile_id].attributes):
            raise ValueError("Assign a rank to every attribute")
        if len(set(self.ranks)) != len(self.ranks):
            raise ValueError("Each attribute rank (1–3) can appear only once")
        return self

    def rank(self, attribute: str) -> int:
        attributes = PROFILES[self.profile_id].attributes
        if attribute not in attributes:
            raise ValueError("Attribute must belong to the current genre kit")
        return self.ranks[attributes.index(attribute)]


# The last box of each row: two wounds, then Defeat. Each is preceded by three strain boxes.
STRAIN_ENDINGS = (3, 7, 11)


class StrainTracker(FrozenModel):
    boxes: tuple[StrictBool, ...] = Field(default=(False,) * 12, min_length=12, max_length=12)
    names: tuple[str, str, str] = ("", "", "")

    @model_validator(mode="after")
    def validate_endings(self) -> Self:
        for ending in STRAIN_ENDINGS:
            if self.boxes[ending] and not all(self.boxes[:ending]):
                raise ValueError("A marked wound needs every earlier box marked")
        return self

    @property
    def defeated(self) -> bool:
        return self.boxes[11]

    @property
    def locked_boxes(self) -> frozenset[int]:
        """Boxes that must stay marked: everything before the last marked wound."""
        marked = [ending for ending in STRAIN_ENDINGS if self.boxes[ending]]
        return frozenset(range(max(marked))) if marked else frozenset()

    def markable(self, index: int) -> bool:
        """A wound can be marked once every box before it is marked; other boxes always."""
        return index not in STRAIN_ENDINGS or all(self.boxes[:index])

    def set_box(self, index: int, checked: bool) -> Self:
        index = TypeAdapter(Index).validate_python(index)
        if index >= len(self.boxes):
            raise ValueError("Strain box is outside the tracker")
        if checked and not self.markable(index):
            raise ValueError("Mark all strain before a wound first")
        if not checked and index in self.locked_boxes:
            raise ValueError("Boxes before a marked wound stay marked until that wound is cleared")
        boxes = list(self.boxes)
        boxes[index] = checked
        return type(self)(boxes=boxes, names=self.names)

    def set_name(self, row: int, name: str) -> Self:
        row = TypeAdapter(Index).validate_python(row)
        if row >= len(self.names):
            raise ValueError("Wound row is outside the tracker")
        names = list(self.names)
        names[row] = name
        return type(self)(boxes=self.boxes, names=names)

    def take(self, points: int) -> Self:
        points = TypeAdapter(Index).validate_python(points)
        boxes = list(self.boxes)
        start = max((index + 1 for index in STRAIN_ENDINGS if boxes[index]), default=0)
        for index in range(start, len(boxes)):
            if points == 0:
                break
            if not boxes[index]:
                boxes[index] = True
                points -= 1
        return type(self)(boxes=boxes, names=self.names)

    def take_wound(self) -> Self:
        """Mark everything up to and including the next unmarked wound (or Defeat)."""
        ending = next((index for index in STRAIN_ENDINGS if not self.boxes[index]), None)
        if ending is None:
            raise ValueError("Defeat is already marked")
        boxes = [index <= ending or marked for index, marked in enumerate(self.boxes)]
        return type(self)(boxes=boxes, names=self.names)


class RollSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: Genre = Genre.CORE
    attributes: AttributeSetup | None = None
    current_result: RollResult | None = None
    tech: TechState | None = None
    total_strain: int = Field(default=0, ge=0)
    total_corruption: int = Field(default=0, ge=0)
    strain: StrainTracker = Field(default_factory=StrainTracker)
    bonuses: NamedBonuses = Field(default_factory=NamedBonuses)
    # Heckboy power names, for the player's reference; they do not change rolls.
    power_names: tuple[str, str] = ("", "")
    # Results before each item or expertise bonus, newest last; not saved and cleared by a roll.
    _before_bonus: list[RollResult] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def validate_attributes(self) -> Self:
        if self.attributes is not None and self.attributes.profile_id != self.profile_id:
            raise ValueError("Attributes must match the session profile")
        return self

    def set_bonus_name(self, kind: BonusKind, name: str) -> NamedBonuses:
        kind = TypeAdapter(BonusKind).validate_python(kind)
        candidate = NamedBonuses.model_validate({**self.bonuses.model_dump(), kind.value: name})
        self.bonuses = candidate
        return candidate

    def set_power_name(self, index: int, name: str) -> None:
        names = list(self.power_names)
        names[index] = name
        self.power_names = tuple(names)

    def _named_bonus_result(self, kind: BonusKind) -> RollResult:
        previous = self.current_result
        if previous is None or previous.request.profile_id != self.profile_id:
            raise ValueError("Roll a test for the current genre kit before applying bonuses")
        if not getattr(self.bonuses, kind.value).strip():
            raise ValueError(f"Name the {kind.value.replace('_', ' ')} before applying it")
        return previous

    def apply_item(self, kind: BonusKind, index: int) -> RollResult:
        kind = TypeAdapter(BonusKind).validate_python(kind)
        if kind == BonusKind.EXPERTISE:
            raise ValueError("Expertise is not an item")
        previous = self._named_bonus_result(kind)
        index = TypeAdapter(Index).validate_python(index)
        if kind in previous.applied_items:
            raise ValueError(f"The {kind.value.replace('_', ' ')} was already used on this test")
        if index >= len(previous.dice):
            raise ValueError("Item target is outside the dice pool")
        dice = list(previous.dice)
        die = dice[index]
        dice[index] = DieResult(raw=die.raw, bonus=die.bonus + 1)
        candidate = previous.model_copy(
            update={"dice": tuple(dice), "applied_items": previous.applied_items | {kind}}
        )
        return self._replace_result(candidate)

    def apply_expertise(self) -> RollResult:
        previous = self._named_bonus_result(BonusKind.EXPERTISE)
        if previous.request.expertise:
            raise ValueError("Expertise has already been applied to this test")
        request = previous.request.model_copy(update={"expertise": True})
        candidate = previous.model_copy(update={"request": request})
        return self._replace_result(candidate)

    def _replace_result(self, candidate: RollResult) -> RollResult:
        self._before_bonus.append(self.current_result)
        self.current_result = candidate
        return candidate

    @property
    def can_undo_bonus(self) -> bool:
        return bool(self._before_bonus)

    def undo_bonus(self) -> RollResult:
        if not self._before_bonus:
            raise ValueError("No item or expertise bonus to undo")
        self.current_result = self._before_bonus.pop()
        return self.current_result

    def configure_attributes(self, ranks: tuple[int, ...]) -> AttributeSetup:
        if self.attributes is not None:
            raise ValueError("Attributes are fixed until changing genre kit")
        candidate = AttributeSetup(profile_id=self.profile_id, ranks=ranks)
        self.attributes = candidate
        return candidate

    def attribute_rank(self, attribute: str) -> int:
        if self.attributes is None:
            raise ValueError("Set attributes before starting the game")
        return self.attributes.rank(attribute)

    def initialize_tech(self) -> TechState:
        if self.profile_id != Genre.SECOND_CONTACT:
            raise ValueError("Only Second Contact can initialize Tech")
        science = self.attribute_rank("Science")
        culture = self.attribute_rank("Culture")
        candidate = TechState(
            science=science,
            culture=culture,
            remaining_bonus=science + culture,
        )
        self.tech = candidate
        return candidate

    def roll(self, request: RollRequest, *, rng: Random) -> RollResult:
        self.validate_roll_request(request)
        bonuses, next_tech = self.dice_bonuses(request)
        candidate = RollResult(
            request=request,
            dice=tuple(DieResult(raw=rng.randint(1, 6), bonus=b) for b in bonuses),
            strain_delta=request.power.cost,
        )
        next_strain = self.strain.take(candidate.strain_delta)
        self.tech = next_tech
        self.strain = next_strain
        self.total_strain += candidate.strain_delta
        self._before_bonus.clear()
        self.current_result = candidate
        return candidate

    def validate_roll_request(self, request: RollRequest) -> None:
        if request.profile_id != self.profile_id:
            raise ValueError("Request must match the session profile")
        if request.attribute_rank != self.attribute_rank(request.attribute):
            raise ValueError("Tested rank must match the assigned attribute value")

    def dice_bonuses(self, request: RollRequest) -> tuple[list[int], TechState | None]:
        """Per-die bonuses for a request and the Tech state after it; changes nothing."""
        bonuses = [0] * request.pool_size()
        tech = self.tech
        if request.tech_target is None:
            return bonuses, tech
        if tech is None or tech.remaining_bonus == 0:
            raise ValueError("Tech is unavailable or depleted; explicitly initialize it first")
        bonuses[request.tech_target] += tech.remaining_bonus
        spent = TechState(
            science=tech.science, culture=tech.culture, remaining_bonus=tech.remaining_bonus - 1
        )
        return bonuses, spent

    def reroll(self, indices: set[int], *, rng: Random) -> RollResult:
        indices = TypeAdapter(set[Index]).validate_python(indices)
        previous = self.current_result
        if self.profile_id != Genre.OLDHEART:
            raise ValueError("Only Oldheart can reroll dice")
        if previous is None or previous.request.profile_id != self.profile_id:
            raise ValueError("Roll an Oldheart test before rerolling")
        if not indices or any(index >= len(previous.dice) for index in indices):
            raise ValueError("Select at least one valid die from the current test")
        candidate = RollResult(
            request=previous.request,
            dice=tuple(
                DieResult(raw=rng.randint(1, 6), bonus=die.bonus) if index in indices else die
                for index, die in enumerate(previous.dice)
            ),
            corruption_delta=len(indices),
            applied_items=previous.applied_items,
        )
        self.total_corruption += candidate.corruption_delta
        self._before_bonus.clear()
        self.current_result = candidate
        return candidate
