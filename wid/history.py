"""Structured action history; text is produced only when an entry is rendered."""

from collections import Counter
from collections.abc import Sequence
from typing import Annotated, Self

from pydantic import Field, model_validator

from wid.formatting import check_summary, describe_dice, summarize, tech_strengths
from wid.profiles import PROFILES
from wid.rolls import FrozenModel, RollResult, TechPiece

Count = Annotated[int, Field(strict=True, ge=0)]
# The action of an entry for a new test, as opposed to a reroll, bonus or undo that changes one.
ROLL_ACTION = "Roll"


class HistoryEntry(FrozenModel):
    """Either a plain notice or an action with the test it produced.

    Session totals are snapshots taken when the action happened.
    """

    notice: str = ""
    action: str = ""
    result: RollResult | None = None
    # False when a bonus, Tech or an undo changes a roll that was already paid for.
    charged: bool = True
    total_strain: Count = 0
    total_corruption: Count = 0
    tech_pieces: tuple[TechPiece, ...] | None = None
    expertise_name: str = ""

    @model_validator(mode="after")
    def validate_kind(self) -> Self:
        if bool(self.notice) == (self.result is not None):
            raise ValueError("History entry needs either a notice or a result.")
        if self.result is None:
            self.reject_action_fields()
        elif not self.action:
            raise ValueError("History entry for a result needs an action.")
        return self

    def reject_action_fields(self) -> None:
        for name, field in type(self).model_fields.items():
            if name != "notice" and getattr(self, name) != field.default:
                raise ValueError(f"A notice cannot set {name}.")

    def __str__(self) -> str:
        result = self.result
        if result is None:
            return self.notice
        request = result.request
        strain = result.strain_delta if self.charged else 0
        corruption = result.corruption_delta if self.charged else 0
        text = (
            f"{self.action}: {request.profile_id.value}, {request.attribute} "
            f"rank {request.attribute_rank}; assisted={request.assisted}, "
            f"fear={request.fear_level}, expertise={request.expertise}, "
            f"power={request.power.value}\n"
        )
        if request.expertise:
            text += f"Expertise name: {self.expertise_name}\n"
        if request.resource_die:
            text += "Resources die: +1d6\n"
        if request.manifestation_dice:
            text += f"Manifestations: {request.manifestation_dice:+d}d6\n"
        text += (
            f"{describe_dice(result)}\n{summarize(result)}\n"
            f"Strain +{strain} (session {self.total_strain})"
        )
        if PROFILES[request.profile_id].has_rerolls:
            text += f"; Corruption +{corruption} (session {self.total_corruption})"
        # Bonuses copy the result they change, check included, but only the reroll made it.
        if self.charged and result.manifestation_check is not None:
            text += f"\n{check_summary(result.manifestation_check)}"
        if self.tech_pieces is not None:
            text += f"; Tech remaining {tech_strengths(self.tech_pieces)}"
        return text


def history_statistics(entries: Sequence[HistoryEntry]) -> str:
    """How the dice have fallen: each test's dice as first rolled, and how big the pools were.

    Only new tests count, and an undone test still counts as first rolled. A reroll's entry
    repeats the dice it kept, and bonuses and undos repeat a whole result, so counting those would
    count the same dice twice. Empty with no rolls yet.
    """
    rolls = [entry.result for entry in entries if entry.action == ROLL_ACTION and entry.result]
    if not rolls:
        return ""
    totals = [result.totals() for result in rolls]
    dice = sum(len(result.dice) for result in rolls)
    hits = sum(total.dice_hits for total in totals)
    misses = sum(total.misses for total in totals)
    fumbles = sum(total.fumbles for total in totals)
    pools = Counter(len(result.dice) for result in rolls)
    sizes = ", ".join(f"{size}d6 ×{count}" for size, count in sorted(pools.items()))
    outcomes = ", ".join(
        (
            counted(hits, "hit", "hits"),
            counted(misses, "miss", "misses"),
            counted(fumbles, "fumble", "fumbles"),
        )
    )
    tests = counted(len(rolls), "test", "tests")
    return f"{tests}, {counted(dice, 'die', 'dice')} as first rolled: {outcomes}. Pools: {sizes}."


def counted(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"
