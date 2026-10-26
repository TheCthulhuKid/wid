"""Plain-text renderings of a roll, shared by the result panel and the history log."""

from wid.profiles import PROFILES
from wid.rolls import (
    MANIFESTATION_EFFECTS,
    RESOURCES_MAX,
    STRAIN_ENDINGS,
    ManifestationCheck,
    Outcome,
    ResourceEffect,
    ResourceSpend,
    RollResult,
    StrainTracker,
    TechPiece,
)

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
    tech_pieces: tuple[TechPiece, ...] | None,
) -> str:
    """Action deltas with session totals; Corruption only for kits that reroll."""
    text = f"Strain: +{result.strain_delta} (session {total_strain})"
    if PROFILES[result.request.profile_id].has_rerolls:
        text += f" | Corruption: +{result.corruption_delta} (session {total_corruption})"
    if tech_pieces is not None:
        text += f" | Tech remaining: {tech_strengths(tech_pieces)}"
    return text


def tech_strengths(pieces: tuple[TechPiece, ...]) -> str:
    """Each piece with its strength, such as ``Tech 1 at 3, Drone at 0``."""
    return ", ".join(
        f"{piece.label(index)} at {piece.strength}" for index, piece in enumerate(pieces)
    )


def check_summary(check: ManifestationCheck) -> str:
    """The dice of a manifestation check and what they mean."""
    outcome = "a manifestation!" if check.triggered else "no manifestation"
    dice = " + ".join(str(die) for die in check.dice)
    return (
        f"Manifestation check: {dice} = {check.total} against Corruption {check.score}, {outcome}"
    )


def manifestation_note(attributes: tuple[str, ...], manifestations: int) -> str:
    """How manifestations change the pools of a kit's attributes, such as ``Depravity +1d6``."""
    effects = [
        f"{attribute} {MANIFESTATION_EFFECTS[attribute] * manifestations:+d}d6"
        for attribute in attributes
        if attribute in MANIFESTATION_EFFECTS and manifestations
    ]
    return f"manifestations: {', '.join(effects)}" if effects else ""


def resources_reminder(result: RollResult) -> str:
    """For kits with Resources, a reminder that hits beyond the first can buy Resources."""
    if not PROFILES[result.request.profile_id].has_resources or result.totals().hits < 2:
        return ""
    return "Extra hits can be spent to gain Resources."


SPEND_EFFECTS = {
    ResourceEffect.EXTRA_DIE: "+1d6 on the next test to confront a Danger or defend against it",
    ResourceEffect.AUTO_PASS: "automatically pass an obstacle that does not involve a Danger",
    ResourceEffect.CRAFT_ITEM: "craft an item; name it under Crafted item",
    ResourceEffect.RECOVER_STRAIN: "recover 1d6 strain",
}


def spend_summary(spend: ResourceSpend, pool: int) -> str:
    """History line for spending a full pool, such as ``Spent 6 Resources: craft an item...``."""
    text = f"Spent {RESOURCES_MAX} Resources: {SPEND_EFFECTS[spend.effect]}"
    if spend.die is not None:
        text += f" (rolled {spend.die}, cleared {spend.recovered} strain)"
    return f"{text}. Resources reset to {pool}."


def strain_counts(tracker: StrainTracker) -> str:
    """Marked strain and wounds, such as ``3 strain, 1 wound``; Defeat is added when marked."""
    wounds = sum(tracker.boxes[ending] for ending in STRAIN_ENDINGS[:-1])
    strain = sum(tracker.boxes) - wounds - tracker.defeated
    text = f"{strain} strain, {wounds} {'wound' if wounds == 1 else 'wounds'}"
    return f"{text} — Defeat" if tracker.defeated else text


def strain_summary(tracker: StrainTracker) -> str:
    """Title of the collapsible strain section, so the state shows while it is folded away."""
    return f"Strain tracker: {strain_counts(tracker)}"
