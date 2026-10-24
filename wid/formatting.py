"""Plain-text renderings of a roll, shared by the result panel and the history log."""

from wid.profiles import PROFILES
from wid.rolls import Outcome, RollResult

# A piece of text and the outcome it should be coloured as, if any.
Part = tuple[str, Outcome | None]


def _plain(parts: list[Part]) -> str:
    return "".join(text for text, _ in parts)


def describe_dice(result: RollResult) -> str:
    """Verbose per-die lines, as written to the history log."""
    return "\n".join(
        f"Die {index + 1}: raw {die.raw} +{die.bonus} = {die.effective} — "
        f"{die.classify(result.request).value}"
        for index, die in enumerate(result.dice)
    )


def dice_parts(result: RollResult) -> list[list[Part]]:
    """Compact per-die lines for the result panel, one list of parts per die."""
    lines: list[list[Part]] = []
    for index, die in enumerate(result.dice):
        outcome = die.classify(result.request)
        lines.append(
            [
                (f"{index + 1}: {die.raw}+{die.bonus}={die.effective} ", None),
                (outcome.value, outcome),
            ]
        )
    return lines


def dice_lines(result: RollResult) -> str:
    return "\n".join(_plain(line) for line in dice_parts(result))


def summary_parts(result: RollResult) -> list[Part]:
    totals = result.totals()
    return [
        (
            f"Hits: {totals.hits} (dice {totals.dice_hits}, expertise {totals.expertise_hits})",
            Outcome.HIT,
        ),
        (" | ", None),
        (f"Misses: {totals.misses}", Outcome.MISS),
        (" | ", None),
        (f"Fumbles: {totals.fumbles}", Outcome.FUMBLE),
    ]


def summarize(result: RollResult) -> str:
    return _plain(summary_parts(result))


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
