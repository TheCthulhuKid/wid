"""Plain-text renderings of the game, shared by every front end and the history log."""

from wid.profiles import PROFILES
from wid.rolls import (
    MANIFESTATION_EFFECTS,
    MANIFESTATION_LIMIT,
    RESOURCES_MAX,
    STRAIN_ENDINGS,
    BonusKind,
    ManifestationCheck,
    Outcome,
    PowerMode,
    ResourceEffect,
    ResourceSpend,
    RollRequest,
    RollResult,
    RollSession,
    StrainTracker,
    TechPiece,
    TechState,
    standing_label,
)

BONUS_LABELS = {
    BonusKind.EXPERTISE: "Expertise",
    BonusKind.APPROPRIATE_ITEM: "Appropriate Item",
    BonusKind.INAPPROPRIATE_ITEM: "Inappropriate Item",
    BonusKind.CRAFTED_ITEM: "Crafted item",
}

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
    if check.succumbed:
        outcome = "no effect: the character has already succumbed"
    else:
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


# The amounts the screens offer for Corruption gained by hand. Any amount is allowed: a reroll
# gains one per die, so it can gain more at once.
CORRUPTION_AMOUNTS = range(1, 7)

POWER_LABELS = {
    PowerMode.RELIABLE: "Reliable power (+1 die, +1 strain)",
    PowerMode.ERRATIC: "Erratic power (+2 dice, +2 strain)",
}

SPEND_EFFECTS = {
    ResourceEffect.EXTRA_DIE: "+1d6 on the next test to confront a Danger or defend against it",
    ResourceEffect.AUTO_PASS: "automatically pass an obstacle that does not involve a Danger",
    ResourceEffect.CRAFT_ITEM: "craft an item; name it under Crafted item",
    ResourceEffect.RECOVER_STRAIN: "recover 1d6 strain",
}


# The effects as choices on screen. They start lower case to fit the middle of a history line,
# and str.capitalize would lower "Crafted item" as well.
SPEND_LABELS = {effect: text[0].upper() + text[1:] for effect, text in SPEND_EFFECTS.items()}


def spend_summary(spend: ResourceSpend, pool: int) -> str:
    """History line for spending a full pool, such as ``Spent 6 Resources: craft an item...``."""
    text = f"Spent {RESOURCES_MAX} Resources: {SPEND_EFFECTS[spend.effect]}"
    if spend.die is not None:
        text += f" (rolled {spend.die}, cleared {spend.recovered} strain)"
    return f"{text}. Resources reset to {pool}."


# What the front ends ask before replacing or losing something.
NEW_GAME_QUESTION = (
    "A genre kit lasts the whole game, so changing it starts a new game: the character, "
    "history, notes and file path are cleared. Unsaved changes will be lost."
)
NEW_CHARACTER_QUESTION = (
    "Start a new character? This clears the character, ranks, items, strain and the current "
    "roll. The history, notes and file path stay."
)
QUIT_QUESTION = "Quit? Unsaved changes will be lost."
RECOVERY_QUESTION = (
    "wid closed last time with unsaved changes, and kept a copy. Restore that game? If not, the "
    "copy stays until this game has something to lose."
)


def recovery_decline(opened: bool) -> str:
    """The button that leaves the recovery copy: for a fresh game, or for a file just opened."""
    return "Keep the opened game" if opened else "Start fresh"


def replace_question(kind: str, path: object) -> str:
    """Asked before writing over a file: ``kind`` is "save" or "file"."""
    return f"Replace the existing {kind} at {path}?"


def load_question(name: str) -> str:
    return f"Load {name}? This replaces the current game and history. Unsaved changes will be lost."


def strain_counts(tracker: StrainTracker) -> str:
    """Marked strain and wounds, such as ``3 strain, 1 wound``; Defeat is added when marked."""
    wounds = sum(tracker.boxes[ending] for ending in STRAIN_ENDINGS[:-1])
    strain = sum(tracker.boxes) - wounds - tracker.defeated
    text = f"{strain} strain, {wounds} {'wound' if wounds == 1 else 'wounds'}"
    return f"{text} — Defeat" if tracker.defeated else text


def strain_notice(change: str, tracker: StrainTracker) -> str:
    """History line for a strain change, such as ``Took 1 strain: 3 strain, 1 wound.``"""
    return f"{change}: {strain_counts(tracker)}."


def strain_summary(tracker: StrainTracker) -> str:
    """Title of the collapsible strain section, so the state shows while it is folded away."""
    return f"Strain tracker: {strain_counts(tracker)}"


def strain_status(tracker: StrainTracker) -> str:
    """The hint under the strain boxes, or Defeat with its name once it is marked."""
    if not tracker.defeated:
        return "Mark strain as it is taken. Mark all the strain before a wound first."
    return f"Defeat — character ended. {tracker.names[2]}".rstrip()


def standing_notice(standing: int) -> str:
    # Three dots share the label Reputable, so the dot says which one.
    return f"Standing moved to {standing_label(standing)} (dot {standing + 1})."


def resources_notice(amount: int, pool: int) -> str:
    return f"Resources {amount:+d}: {pool} in the pool."


def corruption_status(session: RollSession) -> str:
    """Oldheart's Corruption and manifestation count, and whether the character succumbed."""
    status = (
        f"Corruption {session.total_corruption} — {len(session.manifestations)} of "
        f"{MANIFESTATION_LIMIT} manifestations"
    )
    if session.succumbed:
        status += ". Succumbed: the character becomes a Brute Danger for the GM"
    return status


def pool_line(request: RollRequest) -> str:
    """The dice the next test rolls and why, such as ``Pool: 4d6 — hits on 5+``."""
    text = f"Pool: {request.pool_size}d6 — hits on {request.hit_threshold}+"
    if request.resource_die:
        text += " (includes the Resources die)"
    attributes = PROFILES[request.profile_id].attributes
    if note := manifestation_note(attributes, request.manifestations):
        text += f" ({note}; never below 1d6)"
    return text


def tech_starting_line(tech: TechState | None) -> str:
    if tech is None:
        return "Start the game to get your Tech slots."
    return (
        f"Each piece starts at Science {tech.science} + Culture {tech.culture} = "
        f"{tech.starting_strength}."
    )
