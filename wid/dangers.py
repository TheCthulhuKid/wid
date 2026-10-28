"""The GM guide's Danger rules: classes, difficulties, loadouts, a scene's threshold and
activation. What an ability does to a PC is the book's; wid only names it."""

from enum import StrEnum
from random import Random
from typing import Annotated, Self

from pydantic import Field, model_validator

from wid.profiles import PROFILES, Genre
from wid.rolls import FrozenModel, roll_d6


class _Word(StrEnum):
    @property
    def label(self) -> str:
        return self.value.capitalize()


class Ability(_Word):
    HARASS = "harass"
    SCARE = "scare"
    KILL = "kill"
    # One per genre kit, in the order the kits are listed in profiles.py.
    DOMINATE = "dominate"
    EXTERMINATE = "exterminate"
    BLIGHT = "blight"
    MANIPULATE = "manipulate"
    SIEGE = "siege"


class DangerClass(_Word):
    BRUTE = "brute"
    SWARM = "swarm"
    NIGHTMARE = "nightmare"
    DISASTER = "disaster"
    TITAN = "titan"
    OVERLORD = "overlord"
    DEFILER = "defiler"
    SCHEMER = "schemer"
    DEMOLISHER = "demolisher"

    @property
    def abilities(self) -> tuple[Ability, Ability]:
        return CLASS_ABILITIES[self]


# The two abilities a class fills dice 4 and 5 with.
CLASS_ABILITIES = {
    DangerClass.BRUTE: (Ability.KILL, Ability.KILL),
    DangerClass.SWARM: (Ability.HARASS, Ability.SCARE),
    DangerClass.NIGHTMARE: (Ability.SCARE, Ability.SCARE),
    DangerClass.DISASTER: (Ability.KILL, Ability.HARASS),
    DangerClass.TITAN: (Ability.DOMINATE, Ability.DOMINATE),
    DangerClass.OVERLORD: (Ability.EXTERMINATE, Ability.EXTERMINATE),
    DangerClass.DEFILER: (Ability.BLIGHT, Ability.BLIGHT),
    DangerClass.SCHEMER: (Ability.MANIPULATE, Ability.MANIPULATE),
    DangerClass.DEMOLISHER: (Ability.SIEGE, Ability.SIEGE),
}

BASE_CLASSES = (DangerClass.BRUTE, DangerClass.SWARM, DangerClass.NIGHTMARE, DangerClass.DISASTER)
KIT_CLASSES = {
    Genre.HECKBOY: DangerClass.TITAN,
    Genre.SECOND_CONTACT: DangerClass.OVERLORD,
    Genre.OLDHEART: DangerClass.DEFILER,
    Genre.BALL_SEASON: DangerClass.SCHEMER,
    Genre.THIS_ISNT_HAPPENING: DangerClass.DEMOLISHER,
}


def classes_for(genre: Genre) -> tuple[DangerClass, ...]:
    """The four base classes and, in a kit, the class it adds."""
    kit_class = KIT_CLASSES.get(genre)
    return BASE_CLASSES if kit_class is None else BASE_CLASSES + (kit_class,)


class DifficultyRule(FrozenModel):
    """What a difficulty gives a Danger: the ability on die 6, the hits a PC needs to pass a
    test, and the threshold as a multiple of the PC count plus an addend."""

    ability: Ability
    hits_to_pass: int
    multiplier: int
    addend: int = 0

    def threshold(self, pc_count: int) -> int:
        return pc_count * self.multiplier + self.addend


class Difficulty(_Word):
    PETTY = "petty"
    COMPETENT = "competent"
    BOSS = "boss"
    MEGA = "mega"

    @property
    def rule(self) -> DifficultyRule:
        return DIFFICULTY_RULES[self]

    @property
    def rank(self) -> int:
        """Position from petty to mega, to find the strongest Danger in a scene."""
        return list(Difficulty).index(self)


DIFFICULTY_RULES = {
    Difficulty.PETTY: DifficultyRule(
        ability=Ability.HARASS, hits_to_pass=1, multiplier=1, addend=1
    ),
    Difficulty.COMPETENT: DifficultyRule(ability=Ability.HARASS, hits_to_pass=1, multiplier=2),
    Difficulty.BOSS: DifficultyRule(ability=Ability.SCARE, hits_to_pass=2, multiplier=3),
    Difficulty.MEGA: DifficultyRule(ability=Ability.KILL, hits_to_pass=2, multiplier=4),
}

# Dice 1 to 3 of every loadout.
DEFAULT_ABILITIES = (Ability.HARASS, Ability.SCARE, Ability.KILL)


class Replaceable(FrozenModel):
    def replace(self, **changes: object) -> Self:
        """A copy with ``changes``, built anew rather than copied so it is validated."""
        return type(self)(**{**dict(self), **changes})


class Danger(Replaceable):
    name: str = ""
    danger_class: DangerClass
    difficulty: Difficulty

    def label(self, index: int) -> str:
        """The name, or "Danger 1" for the first unnamed Danger."""
        return self.name.strip() or f"Danger {index + 1}"

    @property
    def loadout(self) -> tuple[Ability, ...]:
        """The ability each die picks, from 1 to 6."""
        return DEFAULT_ABILITIES + self.danger_class.abilities + (self.difficulty.rule.ability,)

    @property
    def hits_to_pass(self) -> int:
        return self.difficulty.rule.hits_to_pass

    def threshold(self, pc_count: int) -> int:
        return self.difficulty.rule.threshold(pc_count)


PC_MIN = 1
PC_MAX = 8
DANGERS_MAX = 4
Count = Annotated[int, Field(strict=True, ge=0)]


class Scene(Replaceable):
    """A confrontation: the PCs against every Danger in it, sharing one threshold."""

    pc_count: Annotated[int, Field(strict=True, ge=PC_MIN, le=PC_MAX)] = 4
    dangers: tuple[Danger, ...] = Field(default=(), max_length=DANGERS_MAX)
    progress: Count = 0
    # Added to the Dangers' thresholds, as Ball Season's manipulate does.
    raised: Count = 0
    hostile: bool = False

    @model_validator(mode="after")
    def _within_threshold(self) -> Self:
        if self.progress > self.threshold:
            raise ValueError("Progress cannot exceed the threshold.")
        return self

    @property
    def threshold(self) -> int:
        return sum(danger.threshold(self.pc_count) for danger in self.dangers) + self.raised

    @property
    def strongest(self) -> Danger | None:
        """The Danger whose loadout the scene rolls on; the first of equals."""
        if not self.dangers:
            return None
        return max(self.dangers, key=lambda danger: danger.difficulty.rank)

    @property
    def loadout(self) -> tuple[Ability, ...]:
        return self.strongest.loadout if self.strongest else ()

    @property
    def hits_to_pass(self) -> int:
        return self.strongest.hits_to_pass if self.strongest else 0

    @property
    def overcome(self) -> bool:
        return bool(self.dangers) and self.progress >= self.threshold

    def commit(self, hits: int) -> Self:
        """Progress the threshold by ``hits``, never beyond it."""
        return self.replace(progress=min(self.threshold, self.progress + hits))

    def raise_threshold(self, amount: int) -> Self:
        return self.replace(raised=self.raised + amount)

    def with_pc_count(self, pc_count: int) -> Self:
        """The scene for ``pc_count`` PCs, the progress kept within the lower threshold."""
        scene = self.replace(pc_count=pc_count, progress=0)
        return scene.replace(progress=min(self.progress, scene.threshold))

    def rename(self, index: int, name: str) -> Self:
        danger = self.danger_at(index)
        dangers = (*self.dangers[:index], danger.replace(name=name), *self.dangers[index + 1 :])
        return self.replace(dangers=dangers)

    def without(self, index: int) -> Self:
        """The scene without the Danger at ``index``, the progress kept within the threshold."""
        self.danger_at(index)
        return self._with_dangers(self.dangers[:index] + self.dangers[index + 1 :])

    def danger_at(self, index: int) -> Danger:
        if not 0 <= index < len(self.dangers):
            raise ValueError("No such Danger.")
        return self.dangers[index]

    def in_kit(self, genre: Genre) -> tuple[Self, list[str]]:
        """The scene with only the Dangers ``genre`` has a class for, and the labels of the rest."""
        allowed = classes_for(genre)
        kept = tuple(danger for danger in self.dangers if danger.danger_class in allowed)
        dropped = [
            danger.label(index)
            for index, danger in enumerate(self.dangers)
            if danger.danger_class not in allowed
        ]
        return self._with_dangers(kept), dropped

    def _with_dangers(self, dangers: tuple[Danger, ...]) -> Self:
        scene = self.replace(dangers=dangers, progress=0)
        return scene.replace(progress=min(self.progress, scene.threshold))


# The activation table's Target column, by die. It is the base game's in every kit.
TARGETS = (
    "PC who acted most recently",
    "PC who acted most recently",
    "PC who acted most recently",
    "PC(s) with highest scared",
    "PC(s) with most strain",
    "PC(s) with most wounds",
)
Die = Annotated[int, Field(strict=True, ge=1, le=6)]


def defending_attribute(genre: Genre, die: int) -> str:
    """The kit's attribute the Attribute column names for ``die``: two dice per attribute."""
    return PROFILES[genre].attributes[(die - 1) // 2]


class Activation(FrozenModel):
    """One roll of 3d6: the ability, the target and the defending attribute each die picked."""

    dice: tuple[Die, Die, Die]
    ability: Ability
    target: str
    attribute: str


def activate(scene: Scene, genre: Genre, rng: Random) -> Activation:
    """Roll the ability die, then the target die, then the attribute die."""
    if not scene.dangers:
        raise ValueError("Add a Danger before activating.")
    dice = (roll_d6(rng), roll_d6(rng), roll_d6(rng))
    return Activation(
        dice=dice,
        ability=scene.loadout[dice[0] - 1],
        target=TARGETS[dice[1] - 1],
        attribute=defending_attribute(genre, dice[2]),
    )
