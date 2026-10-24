"""Plain-text renderings of a roll, shared by the result panel and the history log."""

from wid.profiles import PROFILES
from wid.rolls import RollResult


def _per_die(result: RollResult, template: str) -> str:
    return "\n".join(
        template.format(
            n=index + 1,
            raw=die.raw,
            bonus=die.bonus,
            effective=die.effective,
            outcome=die.classify(result.request).value,
        )
        for index, die in enumerate(result.dice)
    )


def describe_dice(result: RollResult) -> str:
    """Verbose per-die lines, as written to the history log."""
    return _per_die(result, "Die {n}: raw {raw} +{bonus} = {effective} — {outcome}")


def dice_lines(result: RollResult) -> str:
    """Compact per-die lines, as shown in the result panel."""
    return _per_die(result, "{n}: {raw}+{bonus}={effective} {outcome}")


def summarize(result: RollResult) -> str:
    totals = result.totals()
    return (
        f"Hits: {totals.hits} (dice {totals.dice_hits}, expertise {totals.expertise_hits}) | "
        f"Misses: {totals.misses} | Fumbles: {totals.fumbles}"
    )


def attribute_label(result: RollResult) -> str:
    return f"{result.request.attribute} (rank {result.request.attribute_rank})"


def resources_line(
    result: RollResult,
    *,
    total_strain: int,
    total_corruption: int,
    tech_remaining: int | None,
) -> str:
    """Action deltas with session totals; Corruption only for kits that reroll."""
    text = f"Strain: +{result.strain_delta} (session {total_strain})"
    if PROFILES[result.request.profile_id].has_rerolls:
        text += f" | Corruption: +{result.corruption_delta} (session {total_corruption})"
    if tech_remaining is not None:
        text += f" | Tech remaining: {tech_remaining}"
    return text
