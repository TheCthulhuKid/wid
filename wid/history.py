"""Structured action history; text is produced only when an entry is rendered."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from wid.profiles import PROFILES
from wid.rolls import FrozenModel, RollResult

Count = Annotated[int, Field(strict=True, ge=0)]


def describe_dice(result: RollResult) -> str:
    return "\n".join(
        f"Die {index + 1}: raw {die.raw} +{die.bonus} = {die.effective} — "
        f"{die.classify(result.request).value}"
        for index, die in enumerate(result.dice)
    )


def summarize(result: RollResult) -> str:
    totals = result.totals()
    return (
        f"Hits: {totals.hits} (dice {totals.dice_hits}, expertise {totals.expertise_hits}) | "
        f"Misses: {totals.misses} | Fumbles: {totals.fumbles}"
    )


class HistoryEntry(FrozenModel):
    """Either a plain notice or an action with the test it produced.

    Session totals are snapshots taken when the action happened.
    """

    notice: str = ""
    action: str = ""
    result: RollResult | None = None
    charged: bool = True  # False for post-roll items, which cost no resources
    total_strain: Count = 0
    total_corruption: Count = 0
    tech_remaining: Count | None = None
    expertise_name: str = ""

    @model_validator(mode="after")
    def validate_kind(self) -> Self:
        if bool(self.notice) == (self.result is not None):
            raise ValueError("History entry needs either a notice or a result")
        if self.result is not None and not self.action:
            raise ValueError("History entry for a result needs an action")
        return self

    def __str__(self) -> str:
        result = self.result
        if result is None:
            return self.notice
        request = result.request
        strain = result.strain_delta if self.charged else 0
        corruption = result.corruption_delta if self.charged else 0
        target = request.tech_target + 1 if request.tech_target is not None else "none"
        text = (
            f"{self.action}: {request.profile_id.value}, {request.attribute} "
            f"rank {request.attribute_rank}; assisted={request.assisted}, "
            f"fear={request.fear_level}, expertise={request.expertise}, "
            f"power={request.power.value}, Tech target={target}\n"
        )
        if request.expertise:
            text += f"Expertise name: {self.expertise_name}\n"
        text += (
            f"{describe_dice(result)}\n{summarize(result)}\n"
            f"Strain +{strain} (session {self.total_strain})"
        )
        if PROFILES[request.profile_id].has_rerolls:
            text += f"; Corruption +{corruption} (session {self.total_corruption})"
        if self.tech_remaining is not None:
            text += f"; Tech remaining {self.tech_remaining}"
        return text
