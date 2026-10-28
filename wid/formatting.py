"""Plain-text renderings of the game, shared by every front end and the history log."""

from collections.abc import Callable

from wid.dangers import TARGETS, Ability, Activation, Danger, Scene, defending_attribute
from wid.profiles import PROFILES, Genre
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
    BonusKind.CRAFTED_ITEM: "Crafted Item",
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


def result_text(result: RollResult) -> str:
    """The result as plain text to paste elsewhere, such as a chat: attribute, dice and totals."""
    return "\n".join((attribute_label(result), describe_dice(result), summarize(result)))


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
    ResourceEffect.CRAFT_ITEM: "craft an item; name it under Crafted Item",
    ResourceEffect.RECOVER_STRAIN: "recover 1d6 strain",
}


# The effects as choices on screen. They start lower case to fit the middle of a history line,
# and str.capitalize would lower "Crafted Item" as well.
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
    "roll. The session name, history, notes and file path stay."
)
GM_KIT_QUESTION = (
    "Change the genre kit? Keep scene keeps the Dangers, history and notes (a Danger of a class "
    "the new kit lacks is dropped). Start new clears them. Unsaved changes will be lost."
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


# Words both front ends show.
CHARACTER_LABELS = {"name": "Name", "looks": "Looks", "nature": "Nature"}
RANKS_HINT = "Give each attribute a different rank (1–3), then start."
NO_RESULT_HINT = "Roll an attribute to see the dice here."


def tech_slot_label(index: int, strength: int) -> str:
    return f"Tech {index + 1}, strength {strength}"


def strain_box_name(index: int) -> str:
    """What strain box ``index`` marks: Defeat at the very end, a Wound at a row's end."""
    if index == STRAIN_ENDINGS[-1]:
        return "Defeat"
    return "Wound" if index in STRAIN_ENDINGS else "Strain"


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


def standing_text(standing: int) -> str:
    # Three dots share the label Reputable, so the dot says which one.
    return f"{standing_label(standing)} (dot {standing + 1})"


def standing_notice(standing: int) -> str:
    return f"Standing moved to {standing_text(standing)}."


def resources_notice(amount: int, pool: int) -> str:
    return f"Resources {amount:+d}: {pool} in the pool."


def corruption_status(session: RollSession, names: str = "") -> str:
    """Oldheart's Corruption and manifestation count, with ``names`` after the count when given,
    and whether the character succumbed."""
    status = (
        f"Corruption {session.total_corruption} — {len(session.manifestations)} of "
        f"{MANIFESTATION_LIMIT} manifestations"
    )
    if names:
        status += f" ({names})"
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


def one_line(text: str) -> str:
    """Typed text on one line with single spaces, so it cannot break a line it is put in."""
    return " ".join(text.split())


def ranks_line(session: RollSession) -> str:
    if session.attributes is None:
        return ""
    attributes = PROFILES[session.profile_id].attributes
    ranks = ", ".join(f"{name} {session.attribute_rank(name)}" for name in attributes)
    return f"Ranks: {ranks}"


def strain_line(session: RollSession) -> str:
    text = f"Strain: {strain_counts(session.strain)}"
    names = [one_line(name) for name in session.strain.names if name.strip()]
    return f"{text} ({', '.join(names)})" if names else text


def bonuses_line(session: RollSession) -> str:
    kinds = [kind for kind in BonusKind if kind != BonusKind.CRAFTED_ITEM or session.item_crafted]
    named = [
        f"{BONUS_LABELS[kind]} {one_line(name)}"
        for kind in kinds
        if (name := getattr(session.bonuses, kind)).strip()
    ]
    return f"Named: {', '.join(named)}" if named else ""


def powers_line(session: RollSession) -> str:
    powers = zip((PowerMode.RELIABLE, PowerMode.ERRATIC), session.power_names)
    named = [f"{one_line(name)} ({mode})" for mode, name in powers if name.strip()]
    return f"Powers: {', '.join(named)}" if named else ""


def tech_line(session: RollSession) -> str:
    return f"Tech: {tech_strengths(session.tech.pieces)}" if session.tech else ""


def corruption_line(session: RollSession) -> str:
    if not PROFILES[session.profile_id].has_rerolls:
        return ""
    names = [one_line(name) for name in session.manifestations if name.strip()]
    return corruption_status(session, ", ".join(names))


def standing_line(session: RollSession) -> str:
    if not PROFILES[session.profile_id].has_standing:
        return ""
    return f"Standing: {standing_text(session.standing)}"


def resources_sheet_line(session: RollSession) -> str:
    if session.resources is None:
        return ""
    waiting = ", with the Resources die waiting" if session.resource_die else ""
    return f"Resources: {session.resources} of {RESOURCES_MAX}{waiting}"


# The lines of the sheet in an export, in order; each is empty when the kit has no such part.
SHEET_LINES: tuple[Callable[[RollSession], str], ...] = (
    ranks_line,
    strain_line,
    bonuses_line,
    powers_line,
    tech_line,
    corruption_line,
    standing_line,
    resources_sheet_line,
)


def sheet_lines(session: RollSession) -> list[str]:
    """The sheet as short lines for an export: ranks, strain, names and the kit's own state."""
    return [text for line in SHEET_LINES if (text := line(session))]


# The GM's scene. The rules behind these numbers are the book's.
NO_DANGER_HINT = "Add a Danger to start the scene."
NO_ACTIVATION_HINT = "Activate the Danger to see its roll here."
LOADOUT_COLUMNS = ("Die", "Ability", "Target", "Attribute")


def hits_text(hits: int) -> str:
    return f"{hits} {'hit' if hits == 1 else 'hits'} to pass"


def danger_summary(danger: Danger, index: int, pc_count: int) -> str:
    """One Danger's line, such as ``Danger 1: Competent Brute — threshold 8, 1 hit to pass``."""
    return (
        f"{one_line(danger.label(index))}: {danger.difficulty.label} {danger.danger_class.label} "
        f"— threshold {danger.threshold(pc_count)}, {hits_text(danger.hits_to_pass)}"
    )


def scene_summary(scene: Scene) -> str:
    """The combined threshold, what is raised and committed, and the strongest Danger's hits."""
    if not scene.dangers:
        return NO_DANGER_HINT
    text = f"Threshold {scene.threshold}"
    if scene.raised:
        text += f" (raised {scene.raised})"
    text += f", progress {scene.progress} — {hits_text(scene.hits_to_pass)}"
    if scene.overcome:
        text += ". Overcome"
    if scene.hostile:
        text += ". Dangers fight each other"
    return text


def activation_line(activation: Activation) -> str:
    """History line for an activation, the three dice in the order they were rolled."""
    dice = ", ".join(str(die) for die in activation.dice)
    return (
        f"Activation ({dice}): {activation.ability.label} — {activation.target}, "
        f"defending with {activation.attribute}"
    )


def loadout_rows(loadout: tuple[Ability, ...], genre: Genre) -> list[tuple[str, str, str, str]]:
    """The activation table for a loadout, a row per die under ``LOADOUT_COLUMNS``."""
    return [
        (str(die), ability.label, TARGETS[die - 1], defending_attribute(genre, die))
        for die, ability in enumerate(loadout, start=1)
    ]
