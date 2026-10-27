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
    ValidationError,
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
    # This Isn't Happening only, once crafted with Resources.
    CRAFTED_ITEM = "crafted_item"


class ResourceEffect(StrEnum):
    """What a full pool of Resources can buy in This Isn't Happening."""

    EXTRA_DIE = "extra_die"
    AUTO_PASS = "auto_pass"
    CRAFT_ITEM = "craft_item"
    RECOVER_STRAIN = "recover_strain"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NamedBonuses(FrozenModel):
    expertise: str = ""
    appropriate_item: str = ""
    inappropriate_item: str = ""
    crafted_item: str = ""


Index = Annotated[int, Field(strict=True, ge=0)]
Rank = Annotated[int, Field(strict=True, ge=1, le=3)]
SCARED_MAX = 3
RESOURCES_MIN = 1
RESOURCES_MAX = 6


def roll_d6(rng: Random) -> int:
    return rng.randint(1, 6)


# Oldheart: the third manifestation means the character succumbs to corruption.
MANIFESTATION_LIMIT = 3
# Dice each manifestation adds to (or takes from) tests of these attributes.
MANIFESTATION_EFFECTS = {"Depravity": 1, "Hospitality": -1}
# The largest pool Oldheart can roll, so the terminal has a reroll box for every die: the base 4,
# plus 1 for Assisted, plus a Depravity die per manifestation. Powers and Resources are other kits'.
OLDHEART_MAX_POOL = 4 + 1 + MANIFESTATION_EFFECTS["Depravity"] * MANIFESTATION_LIMIT


class ManifestationCheck(FrozenModel):
    """One d6 per corruption just gained; a total at or under the new score manifests."""

    dice: tuple[Annotated[int, Field(strict=True, ge=1, le=6)], ...] = Field(min_length=1)
    score: Annotated[int, Field(strict=True, ge=1)]
    # Made after the character succumbed, so a manifestation adds nothing.
    succumbed: bool = False

    @property
    def total(self) -> int:
        return sum(self.dice)

    @property
    def triggered(self) -> bool:
        return self.total <= self.score


def manifestation_check(
    amount: int, score: int, rng: Random, *, succumbed: bool = False
) -> ManifestationCheck:
    dice = tuple(roll_d6(rng) for _ in range(amount))
    return ManifestationCheck(dice=dice, score=score, succumbed=succumbed)


class RollRequest(FrozenModel):
    profile_id: Genre = Genre.CORE
    assisted: bool = False
    fear_level: Annotated[int, Field(strict=True, ge=0, le=SCARED_MAX)] = 0
    attribute_rank: Rank = 1
    attribute: str = "Athleticism"
    expertise: bool = False
    power: PowerMode = PowerMode.NONE
    # A +1d6 bought with a full pool of Resources (This Isn't Happening).
    resource_die: bool = False
    # Oldheart manifestations the character had when rolling; they change some pools.
    manifestations: Annotated[int, Field(strict=True, ge=0, le=MANIFESTATION_LIMIT)] = 0

    @property
    def manifestation_dice(self) -> int:
        return MANIFESTATION_EFFECTS.get(self.attribute, 0) * self.manifestations

    @property
    def pool_size(self) -> int:
        pool = 4 - self.fear_level + int(self.assisted) + self.power.cost + int(self.resource_die)
        # Whatever takes dice away, a test always rolls at least one.
        return max(1, pool + self.manifestation_dice)

    @property
    def hit_threshold(self) -> int:
        return 4 if self.assisted else 5

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        self.validate_power()
        if self.resource_die and not PROFILES[self.profile_id].has_resources:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Resources")
        if self.manifestations and not PROFILES[self.profile_id].has_rerolls:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no manifestations")
        return self

    def validate_power(self) -> None:
        if self.power != PowerMode.NONE and self.profile_id != Genre.HECKBOY:
            raise ValueError("Only Heckboy can use powers")


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
    # Slots of the Tech pieces used on this test; each piece alters one die per test.
    applied_tech: frozenset[Index] = frozenset()
    # The check made for the corruption a reroll inflicted.
    manifestation_check: ManifestationCheck | None = None

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        if len(self.dice) != self.request.pool_size:
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


class TechPiece(FrozenModel):
    """A Tech slot; it stays empty until the player names it, which defines the piece."""

    name: str = ""
    strength: Annotated[int, Field(strict=True, ge=0)] = 0

    @property
    def defined(self) -> bool:
        return bool(self.name.strip())

    @property
    def working(self) -> bool:
        """Named and not yet depleted, so it can be used or sacrificed."""
        return self.defined and self.strength > 0

    def label(self, index: int) -> str:
        return self.name.strip() or f"Tech {index + 1}"


class TechState(FrozenModel):
    """The character's pieces of Tech: one slot per Muscle rank, each with its own strength."""

    science: Rank
    culture: Rank
    pieces: tuple[TechPiece, ...] = Field(min_length=1, max_length=3)

    @property
    def starting_strength(self) -> int:
        return self.science + self.culture

    @model_validator(mode="after")
    def validate_strengths(self) -> Self:
        if any(piece.strength > self.starting_strength for piece in self.pieces):
            raise ValueError("Tech strength exceeds its starting bonus")
        return self

    def piece(self, index: int) -> TechPiece:
        index = TypeAdapter(Index).validate_python(index)
        if index >= len(self.pieces):
            raise ValueError("No such Tech piece")
        return self.pieces[index]

    def with_piece(self, index: int, piece: TechPiece) -> Self:
        pieces = list(self.pieces)
        pieces[index] = piece
        return self.model_copy(update={"pieces": tuple(pieces)})


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


# Ball Season's Standing track, from left to right; the game starts on the centre dot.
STANDING_LABELS = ("Esteemed", "Reputable", "Reputable", "Reputable", "Scandalous")
STANDING_START = 2
Standing = Annotated[int, Field(strict=True, ge=0, le=len(STANDING_LABELS) - 1)]


def standing_label(standing: int) -> str:
    return STANDING_LABELS[standing]


# The last box of each row: two wounds, then Defeat. Each is preceded by three strain boxes.
STRAIN_ENDINGS = (3, 7, 11)
LOCKED_NOTE = "Locked: boxes before a marked wound stay marked until that wound is cleared."
NOT_READY_NOTE = "Mark all the strain before this wound first."


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

    def lock_reason(self, index: int) -> str | None:
        """Why box ``index`` cannot change now, or None when the player may tick or clear it."""
        if index in self.locked_boxes:
            return LOCKED_NOTE
        # A wound can be marked once every box before it is marked; other boxes always.
        if not self.boxes[index] and index in STRAIN_ENDINGS and not all(self.boxes[:index]):
            return NOT_READY_NOTE
        return None

    def set_box(self, index: int, checked: bool) -> Self:
        index = TypeAdapter(Index).validate_python(index)
        if index >= len(self.boxes):
            raise ValueError("Strain box is outside the tracker")
        if checked != self.boxes[index] and (reason := self.lock_reason(index)):
            raise ValueError(reason)
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

    def take_by_hand(self) -> Self:
        """Take 1 strain from the strain button; a strain-costing roll calls ``take`` instead."""
        # Taking strain starts after the last marked wound, so after Defeat nothing is left.
        if self.defeated:
            raise ValueError("Defeat is already marked")
        return self.take(1)

    def recover(self, points: int) -> Self:
        """Unmark up to ``points`` of the newest strain; wounds and locked boxes stay marked."""
        points = TypeAdapter(Index).validate_python(points)
        boxes = list(self.boxes)
        for index in reversed(range(len(boxes))):
            if points == 0:
                break
            if boxes[index] and index not in STRAIN_ENDINGS and index not in self.locked_boxes:
                boxes[index] = False
                points -= 1
        return type(self)(boxes=boxes, names=self.names)

    def take_wound(self) -> Self:
        """Mark everything up to and including the next unmarked wound (or Defeat)."""
        ending = next((index for index in STRAIN_ENDINGS if not self.boxes[index]), None)
        if ending is None:
            raise ValueError("Defeat is already marked")
        boxes = [index <= ending or marked for index, marked in enumerate(self.boxes)]
        return type(self)(boxes=boxes, names=self.names)


def raised_die(result: RollResult, index: int, amount: int) -> tuple[DieResult, ...]:
    """The result's dice with ``amount`` added to the die at ``index``."""
    index = TypeAdapter(Index).validate_python(index)
    if index >= len(result.dice):
        raise ValueError("That die is outside the dice pool")
    dice = list(result.dice)
    dice[index] = DieResult(raw=dice[index].raw, bonus=dice[index].bonus + amount)
    return tuple(dice)


class ResourceSpend(FrozenModel):
    """What spending a full pool of Resources did."""

    effect: ResourceEffect
    # The 1d6 rolled to recover strain, and the strain boxes it cleared.
    die: Annotated[int, Field(ge=1, le=6)] | None = None
    recovered: Annotated[int, Field(ge=0)] = 0


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
    # Ball Season only; it sets the GM's target numbers, so it never changes a roll here.
    standing: Standing = STANDING_START
    # This Isn't Happening only: the pool starts at the Charity rank when the game starts.
    resources: Annotated[int, Field(strict=True, ge=RESOURCES_MIN, le=RESOURCES_MAX)] | None = None
    # A +1d6 bought with Resources, waiting for the next test.
    resource_die: bool = False
    # Whether the third item, bought with Resources, has been crafted.
    item_crafted: bool = False
    # Oldheart: one optional name per manifestation, oldest first.
    manifestations: tuple[str, ...] = Field(default=(), max_length=MANIFESTATION_LIMIT)
    # Results before each bonus, newest last, with the Tech slot the bonus spent, if any.
    # Not saved; cleared by a roll and by anything else that changes the Tech.
    _before_bonus: list[tuple[RollResult, int | None]] = PrivateAttr(default_factory=list)

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
        index = TypeAdapter(Index).validate_python(index)
        if index >= len(self.power_names):
            raise ValueError("No such power")
        names = list(self.power_names)
        names[index] = name
        self.power_names = tuple(names)

    def set_standing(self, standing: int) -> int:
        if not PROFILES[self.profile_id].has_standing:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Standing")
        try:
            standing = TypeAdapter(Standing).validate_python(standing)
        except ValidationError as error:
            raise ValueError("Standing runs from Esteemed (dot 1) to Scandalous (dot 5)") from error
        self.standing = standing
        return standing

    def _current_test(self) -> RollResult:
        previous = self.current_result
        if previous is None or previous.request.profile_id != self.profile_id:
            raise ValueError("Roll a test for the current genre kit before applying bonuses")
        return previous

    def _named_bonus_result(self, kind: BonusKind) -> RollResult:
        previous = self._current_test()
        if not getattr(self.bonuses, kind.value).strip():
            raise ValueError(f"Name the {kind.value.replace('_', ' ')} before applying it")
        return previous

    def apply_item(self, kind: BonusKind, index: int) -> RollResult:
        kind = TypeAdapter(BonusKind).validate_python(kind)
        if kind == BonusKind.EXPERTISE:
            raise ValueError("Expertise is not an item")
        if not PROFILES[self.profile_id].uses_items:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no items")
        if kind == BonusKind.CRAFTED_ITEM and not self.item_crafted:
            raise ValueError(f"Spend {RESOURCES_MAX} Resources to craft an item first")
        previous = self._named_bonus_result(kind)
        if kind in previous.applied_items:
            raise ValueError(f"The {kind.value.replace('_', ' ')} was already used on this test")
        dice = raised_die(previous, index, 1)
        candidate = previous.model_copy(
            update={"dice": dice, "applied_items": previous.applied_items | {kind}}
        )
        return self._replace_result(candidate)

    def apply_tech(self, index: int, die: int) -> RollResult:
        """Add a defined piece's strength to one die of the current test, then weaken it by 1."""
        previous = self._current_test()
        if self.tech is None:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Tech")
        piece = self.tech.piece(index)
        if not piece.defined:
            raise ValueError(f"Name Tech {index + 1} before using it")
        if piece.strength == 0:
            raise ValueError(f"{piece.label(index)} is depleted")
        if index in previous.applied_tech:
            raise ValueError(f"{piece.label(index)} was already used on this test")
        candidate = previous.model_copy(
            update={
                "dice": raised_die(previous, die, piece.strength),
                "applied_tech": previous.applied_tech | {index},
            }
        )
        spent = TechPiece(name=piece.name, strength=piece.strength - 1)
        self.tech = self.tech.with_piece(index, spent)
        return self._replace_result(candidate, tech_slot=index)

    def apply_expertise(self) -> RollResult:
        previous = self._named_bonus_result(BonusKind.EXPERTISE)
        if previous.request.expertise:
            raise ValueError("Expertise has already been applied to this test")
        request = previous.request.model_copy(update={"expertise": True})
        candidate = previous.model_copy(update={"request": request})
        return self._replace_result(candidate)

    def _replace_result(self, candidate: RollResult, *, tech_slot: int | None = None) -> RollResult:
        self._before_bonus.append((self.current_result, tech_slot))
        self.current_result = candidate
        return candidate

    @property
    def can_undo_bonus(self) -> bool:
        return bool(self._before_bonus)

    def undo_bonus(self) -> RollResult:
        if not self._before_bonus:
            raise ValueError("No bonus to undo")
        self.current_result, tech_slot = self._before_bonus.pop()
        if tech_slot is not None:
            piece = self.tech.pieces[tech_slot]
            restored = TechPiece(name=piece.name, strength=piece.strength + 1)
            self.tech = self.tech.with_piece(tech_slot, restored)
        return self.current_result

    def configure_attributes(self, ranks: tuple[int, ...]) -> AttributeSetup:
        if self.attributes is not None:
            raise ValueError("Attributes are fixed until changing genre kit")
        candidate = AttributeSetup(profile_id=self.profile_id, ranks=ranks)
        self.attributes = candidate
        if PROFILES[self.profile_id].has_tech:
            self.start_scenario()
        if PROFILES[self.profile_id].has_resources:
            self.resources = self.attribute_rank("Charity")
        return candidate

    def _pool(self) -> int:
        if self.resources is None:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Resources")
        return self.resources

    def adjust_resources(self, amount: int) -> int:
        """Add to or take from the pool, for taxes, Danger abilities and hits spent on it."""
        pool = self._pool() + amount
        if pool > RESOURCES_MAX:
            raise ValueError(f"Resources cannot go above {RESOURCES_MAX}")
        if pool < RESOURCES_MIN:
            raise ValueError(f"Resources cannot go below {RESOURCES_MIN}")
        self.resources = pool
        return pool

    def spend_resources(self, effect: ResourceEffect, *, rng: Random) -> ResourceSpend:
        """Spend a full pool on ``effect``, then reset the pool to the Charity rank."""
        effect = TypeAdapter(ResourceEffect).validate_python(effect)
        if self._pool() < RESOURCES_MAX:
            raise ValueError(f"Spending needs a full pool of {RESOURCES_MAX} Resources")
        gain = {
            ResourceEffect.EXTRA_DIE: self._arm_resource_die,
            ResourceEffect.AUTO_PASS: lambda _rng: ResourceSpend(effect=ResourceEffect.AUTO_PASS),
            ResourceEffect.CRAFT_ITEM: self._craft_item,
            ResourceEffect.RECOVER_STRAIN: self._recover_strain,
        }[effect]
        spend = gain(rng)
        self.resources = self.attribute_rank("Charity")
        return spend

    def _arm_resource_die(self, _rng: Random) -> ResourceSpend:
        if self.resource_die:
            raise ValueError("A Resources die is already waiting for the next test")
        self.resource_die = True
        return ResourceSpend(effect=ResourceEffect.EXTRA_DIE)

    def _craft_item(self, _rng: Random) -> ResourceSpend:
        if self.item_crafted:
            raise ValueError("You already carry the most items you can (3)")
        self.item_crafted = True
        return ResourceSpend(effect=ResourceEffect.CRAFT_ITEM)

    def _recover_strain(self, rng: Random) -> ResourceSpend:
        die = roll_d6(rng)
        recovered = self.strain.recover(die)
        cleared = sum(self.strain.boxes) - sum(recovered.boxes)
        self.strain = recovered
        return ResourceSpend(effect=ResourceEffect.RECOVER_STRAIN, die=die, recovered=cleared)

    def _check_corruption_kit(self) -> None:
        if not PROFILES[self.profile_id].has_rerolls:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Corruption")

    def add_corruption(self, amount: int, *, rng: Random) -> ManifestationCheck:
        """Gain corruption in one go and make the manifestation check it calls for."""
        self._check_corruption_kit()
        amount = TypeAdapter(Annotated[int, Field(strict=True, ge=1)]).validate_python(amount)
        score = self.total_corruption + amount
        check = manifestation_check(amount, score, rng, succumbed=self.succumbed)
        self.total_corruption += amount
        if check.triggered and not check.succumbed:
            self.manifestations = (*self.manifestations, "")
        return check

    @property
    def in_play(self) -> bool:
        """Whether play has changed anything: ranks, strain, Corruption or Standing."""
        changes = (
            self.attributes is not None,
            self.total_strain,
            self.total_corruption,
            any(self.strain.boxes),
            self.manifestations,
            self.standing != STANDING_START,
        )
        return any(changes)

    @property
    def succumbed(self) -> bool:
        return len(self.manifestations) >= MANIFESTATION_LIMIT

    def add_manifestation(self) -> None:
        """A manifestation from outside a check, such as delivering an undesirable quarry."""
        self._check_corruption_kit()
        if self.succumbed:
            raise ValueError("The character has already succumbed to corruption")
        self.manifestations = (*self.manifestations, "")

    def remove_manifestation(self) -> None:
        """Correct a manifestation added by mistake; the newest goes first."""
        if not self.manifestations:
            raise ValueError("There is no manifestation to remove")
        self.manifestations = self.manifestations[:-1]

    def set_strain_name(self, row: int, name: str) -> None:
        self.strain = self.strain.set_name(row, name)

    def set_manifestation_name(self, index: int, name: str) -> None:
        index = TypeAdapter(Index).validate_python(index)
        if index >= len(self.manifestations):
            raise ValueError("No such manifestation")
        names = list(self.manifestations)
        names[index] = name
        self.manifestations = tuple(names)

    def lose_crafted_item(self) -> None:
        """Drop the crafted item, which frees its slot for another one."""
        if not self.item_crafted:
            raise ValueError("There is no crafted item to lose")
        self.item_crafted = False
        self.bonuses = self.bonuses.model_copy(update={"crafted_item": ""})

    def attribute_rank(self, attribute: str) -> int:
        if self.attributes is None:
            raise ValueError("Set attributes before starting the game")
        return self.attributes.rank(attribute)

    def start_scenario(self) -> TechState:
        """Empty every Tech slot (one per Muscle rank); a slot gives Science + Culture when used."""
        if not PROFILES[self.profile_id].has_tech:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Tech")
        science = self.attribute_rank("Science")
        culture = self.attribute_rank("Culture")
        candidate = TechState(
            science=science,
            culture=culture,
            pieces=(TechPiece(strength=science + culture),) * self.attribute_rank("Muscle"),
        )
        self.tech = candidate
        # An undo would hand strength back to a slot that has been emptied.
        self._before_bonus.clear()
        return candidate

    def set_tech_name(self, index: int, name: str) -> TechState:
        if self.tech is None:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Tech")
        piece = self.tech.piece(index)
        candidate = self.tech.with_piece(index, TechPiece(name=name, strength=piece.strength))
        self.tech = candidate
        return candidate

    def sacrifice_tech(self, index: int) -> TechPiece:
        """Drop a piece to 0 strength to stop a Danger's extermination; returns it as it was."""
        if self.tech is None:
            raise ValueError(f"{PROFILES[self.profile_id].name} has no Tech")
        piece = self.tech.piece(index)
        if not piece.defined:
            raise ValueError(f"Name Tech {index + 1} before sacrificing it")
        if piece.strength == 0:
            raise ValueError(f"{piece.label(index)} is already at 0")
        self.tech = self.tech.with_piece(index, TechPiece(name=piece.name, strength=0))
        # An undo would hand strength back to the sacrificed piece.
        self._before_bonus.clear()
        return piece

    def roll(self, request: RollRequest, *, rng: Random) -> RollResult:
        self.validate_roll_request(request)
        candidate = RollResult(
            request=request,
            dice=tuple(DieResult(raw=roll_d6(rng)) for _ in range(request.pool_size)),
            strain_delta=request.power.cost,
        )
        next_strain = self.strain.take(candidate.strain_delta)
        self.strain = next_strain
        if request.resource_die:
            self.resource_die = False
        self.total_strain += candidate.strain_delta
        self._before_bonus.clear()
        self.current_result = candidate
        return candidate

    def validate_roll_request(self, request: RollRequest) -> None:
        if request.profile_id != self.profile_id:
            raise ValueError("Request must match the session profile")
        if request.attribute_rank != self.attribute_rank(request.attribute):
            raise ValueError("Tested rank must match the assigned attribute value")
        if request.resource_die and not self.resource_die:
            raise ValueError("No Resources die is waiting; spend a full pool first")
        if request.manifestations != len(self.manifestations):
            raise ValueError("Tested manifestations must match the character's")

    def reroll(self, indices: set[int], *, rng: Random) -> RollResult:
        indices = TypeAdapter(set[Index]).validate_python(indices)
        previous = self.current_result
        if self.profile_id != Genre.OLDHEART:
            raise ValueError("Only Oldheart can reroll dice")
        if previous is None or previous.request.profile_id != self.profile_id:
            raise ValueError("Roll an Oldheart test before rerolling")
        if not indices or any(index >= len(previous.dice) for index in indices):
            raise ValueError("Select at least one valid die from the current test")
        dice = tuple(
            DieResult(raw=roll_d6(rng), bonus=die.bonus) if index in indices else die
            for index, die in enumerate(previous.dice)
        )
        candidate = RollResult(
            request=previous.request,
            dice=dice,
            corruption_delta=len(indices),
            applied_items=previous.applied_items,
            applied_tech=previous.applied_tech,
            manifestation_check=self.add_corruption(len(indices), rng=rng),
        )
        self._before_bonus.clear()
        self.current_result = candidate
        return candidate
