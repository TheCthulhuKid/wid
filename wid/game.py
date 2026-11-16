"""The player's game: the character sheet and its actions, on top of ``BaseGame``."""

from collections.abc import Callable, Iterable
from pathlib import Path
from random import Random
from typing import Any, Literal

from wid.base_game import BaseGame
from wid.dangers import Difficulty, recovery_amount
from wid.formatting import (
    BONUS_LABELS,
    check_summary,
    recovery_notice,
    resources_gained,
    resources_notice,
    sheet_lines,
    spend_summary,
    standing_notice,
    strain_notice,
)
from wid.history import ROLL_ACTION, HistoryEntry
from wid.profiles import PROFILES, Genre, Recovers, WiDProfile
from wid.rolls import (
    SACRIFICE_RESOURCES,
    SCARED_MAX,
    BonusKind,
    PowerMode,
    ResourceEffect,
    RollRequest,
    RollResult,
    RollSession,
    Standing,
)
from wid.sessions import CharacterDetails, SavedSession, parse_save

type NameField = Literal["bonus", "power", "manifestation", "tech", "strain"]

# The session setter for each name the player types; the slot is the bonus kind for bonuses
# and the row or index for the others.
RENAMERS: dict[NameField, Callable[[RollSession, Any, str], object]] = {
    "bonus": RollSession.set_bonus_name,
    "power": RollSession.set_power_name,
    "manifestation": RollSession.set_manifestation_name,
    "tech": RollSession.set_tech_name,
    "strain": RollSession.set_strain_name,
}

type NameSlot = tuple[NameField, int | BonusKind]


class Game(BaseGame):
    """The player's game: the character sheet, the options for the next test and its actions."""

    def __init__(self, *, rng: Random | None = None, recovery_path: Path | None = None):
        super().__init__(rng=rng, recovery_path=recovery_path)
        self.reset_sheet(Genre.CORE)

    def reset_sheet(self, genre: Genre) -> None:
        """A fresh character of ``genre``: session, details and the options for the next test."""
        self.session = RollSession(profile_id=genre)
        self.character = CharacterDetails()
        self.tested_attribute = PROFILES[genre].attributes[0]
        self.fear_level = 0
        self.assisted = False
        self.expertise = False
        self.power = PowerMode.NONE
        self.target_standing: Standing | None = None
        # Choices about the current result, kept so a save can restore them.
        self.reroll_selection: tuple[int, ...] = ()
        self.item_target: int | None = None
        # A new sheet has nothing to take back.
        self.undo_stack = []

    @property
    def state(self) -> RollSession:
        return self.session

    @property
    def in_play(self) -> bool:
        return self.session.in_play

    @property
    def savable(self) -> bool:
        return self.session.attributes is not None

    @property
    def profile(self) -> WiDProfile:
        return PROFILES[self.session.profile_id]

    def log_result(self, result: RollResult, action: str, *, charged: bool = True) -> None:
        session = self.session
        self.record(
            HistoryEntry(
                action=action,
                result=result,
                charged=charged,
                total_strain=session.total_strain,
                total_corruption=session.total_corruption,
                tech_pieces=session.tech.pieces if session.tech else None,
                expertise_name=session.bonuses.expertise,
            )
        )
        self.reroll_selection = ()
        # A new roll can have fewer dice than the one the item was aimed at.
        if self.item_target is not None and self.item_target >= self.dice_count:
            self.item_target = None

    @property
    def dice_count(self) -> int:
        result = self.session.current_result
        return len(result.dice) if result is not None else 0

    def set_test_options(
        self,
        *,
        fear_level: int,
        assisted: bool,
        expertise: bool,
        power: PowerMode,
        reroll: Iterable[int],
        item_target: int | None,
        target_standing: Standing | None = None,
    ) -> None:
        """Take the options for the next test and the dice picked from the current result.

        Scared off its track is refused. A die the current result does not have is dropped, since
        a front end may still show the dice of an earlier roll, and so are rerolls in a kit
        without them.
        """
        if not 0 <= fear_level <= SCARED_MAX:
            raise ValueError(f"Scared runs from 0 to {SCARED_MAX}.")
        count = self.dice_count
        self.fear_level = fear_level
        self.assisted = assisted
        self.expertise = expertise
        self.power = power
        self.target_standing = target_standing if self.profile.has_standing else None
        picked = {index for index in reroll if 0 <= index < count}
        self.reroll_selection = tuple(sorted(picked)) if self.profile.has_rerolls else ()
        on_a_die = item_target is not None and 0 <= item_target < count
        self.item_target = item_target if on_a_die else None

    def rename(self, field: NameField, slot: int | BonusKind, name: str) -> None:
        """Name a bonus, power, manifestation, Tech piece or strain row; nothing is logged."""
        RENAMERS[field](self.session, slot, name)

    def typed_names(self, state: RollSession) -> dict[NameSlot, str]:
        """Every name the player types into ``state``, by the field and slot ``RENAMERS`` take."""
        pieces = state.tech.pieces if state.tech else ()
        return {
            **{("bonus", kind): getattr(state.bonuses, kind.value) for kind in BonusKind},
            **{("power", index): name for index, name in enumerate(state.power_names)},
            **{("manifestation", index): name for index, name in enumerate(state.manifestations)},
            **{("tech", index): piece.name for index, piece in enumerate(pieces)},
            **{("strain", row): name for row, name in enumerate(state.strain.names)},
        }

    def draft_request(self, *, preview: bool = False) -> RollRequest:
        """The next test as the options stand; ``preview`` skips the rank, which needs setup."""
        session = self.session
        return RollRequest(
            profile_id=session.profile_id,
            attribute=self.tested_attribute,
            attribute_rank=1 if preview else session.attribute_rank(self.tested_attribute),
            assisted=self.assisted,
            fear_level=self.fear_level,
            expertise=self.expertise,
            power=self.power if self.profile.has_powers else PowerMode.NONE,
            resource_die=session.resource_die,
            manifestations=len(session.manifestations),
            standing=session.standing,
            target_standing=self.target_standing,
        )

    def start_game(self, ranks: tuple[int, ...]) -> str:
        self.session.configure_attributes(ranks)
        return "Attributes set for this game; press Roll beside an attribute."

    def roll(self, attribute: str | None = None) -> str:
        """Test ``attribute``, or the last tested one again; one-test options are then cleared."""
        with self.undoable("roll", options=True):
            if attribute is not None:
                self.session.attribute_rank(attribute)
                self.tested_attribute = attribute
            result = self.session.roll(self.draft_request(), rng=self.rng)
            self.log_result(result, ROLL_ACTION)
            self.assisted = self.expertise = False
            self.power = PowerMode.NONE
            self.target_standing = None
        return ""

    def reroll(self, indices: set[int]) -> str:
        with self.undoable("reroll"):
            result = self.session.reroll(indices, rng=self.rng)
            self.log_result(result, f"Reroll dice {', '.join(str(i + 1) for i in sorted(indices))}")
        return check_summary(result.manifestation_check)

    def apply_bonus(self, kind: BonusKind, die: int) -> str:
        """Expertise adds a hit; an item adds 1 to ``die``."""
        name = getattr(self.session.bonuses, kind)
        with self.undoable("bonus"):
            if kind == BonusKind.EXPERTISE:
                result = self.session.apply_expertise()
                action = f"Expertise {name}: +1 hit"
            else:
                result = self.session.apply_item(kind, die)
                action = f"{BONUS_LABELS[kind]} {name}: +1 to die {die + 1}"
            self.log_result(result, action, charged=False)
        return ""

    def bonus_available(self, kind: BonusKind) -> bool:
        """Whether the bonus is named and still unused on the current test."""
        session = self.session
        result = session.current_result
        if result is None or not getattr(session.bonuses, kind).strip():
            return False
        if kind == BonusKind.EXPERTISE:
            return not result.request.expertise
        if kind == BonusKind.CRAFTED_ITEM and not session.item_crafted:
            return False
        return kind not in result.applied_items

    def apply_tech(self, index: int, die: int) -> str:
        with self.undoable("Tech use"):
            result = self.session.apply_tech(index, die)
            piece = self.session.tech.pieces[index]
            # Using a piece weakens it by 1, so the bonus it gave was one more than it has left.
            action = f"Tech {piece.label(index)}: +{piece.strength + 1} to die {die + 1}"
            self.log_result(result, action, charged=False)
        return ""

    def tech_usable(self, index: int) -> bool:
        """Whether Tech slot ``index`` holds a named, working piece unused on the current test."""
        result = self.session.current_result
        return (
            self.session.tech.pieces[index].working
            and result is not None
            and index not in result.applied_tech
        )

    def set_strain_box(self, index: int, marked: bool) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.set_box(index, marked)
        change = "Marked" if marked else "Cleared"
        return self.notice(strain_notice(f"{change} strain box {index + 1}", self.session.strain))

    def take_strain(self) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.take_by_hand()
        return self.notice(strain_notice("Took 1 strain", self.session.strain))

    def take_wound(self) -> str:
        with self.undoable("strain change"):
            self.session.strain = self.session.strain.take_wound()
        return self.notice(strain_notice("Took a wound", self.session.strain))

    def second_wind(self) -> str:
        with self.undoable("Second Wind"):
            cleared = self.session.second_wind()
        return self.notice(
            strain_notice(f"Second Wind: cleared {cleared} strain", self.session.strain)
        )

    def start_scenario(self) -> str:
        with self.undoable("new scenario"):
            tech = self.session.start_scenario()
        return self.notice(f"New scenario: {len(tech.pieces)} empty Tech slot(s).")

    def sacrifice_tech(self, index: int) -> str:
        with self.undoable("sacrifice"):
            piece = self.session.sacrifice_tech(index)
        return self.notice(f"Sacrificed {piece.label(index)}: strength {piece.strength} → 0.")

    def adjust_resources(self, amount: int) -> str:
        with self.undoable("Resources change"):
            pool = self.session.adjust_resources(amount)
        return self.notice(resources_notice(amount, pool))

    def spend_resources(self, effect: ResourceEffect) -> str:
        with self.undoable("Resources spend"):
            spend = self.session.spend_resources(effect, rng=self.rng)
        return self.notice(spend_summary(spend, self.session.resources))

    def recover_after(self, difficulty: Difficulty) -> str:
        """Recovery after a Danger is overcome, as the kit states it: strain or Resources."""
        amount = recovery_amount(self.session.profile_id, difficulty)
        with self.undoable("recovery"):
            if self.profile.recovers == Recovers.RESOURCES:
                gained = self.session.gain_resources(amount)
                change = resources_gained(gained, amount, self.session.resources)
            else:
                cleared = self.session.recover_strain(amount)
                change = strain_notice(f"cleared {cleared} strain", self.session.strain)
        return self.notice(recovery_notice(difficulty, change))

    def build_barricade(self, spent: int) -> str:
        with self.undoable("barricade"):
            strength = self.session.spend_on_barricade(spent, build=True)
        return self.notice(
            f"Built a barricade of strength {strength} for {spent} Resources: "
            f"{self.session.resources} in the pool."
        )

    def strengthen_barricade(self, spent: int) -> str:
        with self.undoable("barricade"):
            strength = self.session.spend_on_barricade(spent, build=False)
        return self.notice(
            f"Strengthened the barricade by {strength} for {spent} Resources: "
            f"{self.session.resources} in the pool."
        )

    def sacrifice_item(self, kind: BonusKind) -> str:
        name = getattr(self.session.bonuses, kind).strip()
        with self.undoable("sacrifice"):
            gained = self.session.sacrifice_item(kind)
        change = resources_gained(gained, SACRIFICE_RESOURCES, self.session.resources)
        return self.notice(f"Sacrificed {BONUS_LABELS[kind]} {name}: {change}")

    def lose_crafted_item(self) -> str:
        with self.undoable("lost crafted item"):
            self.session.lose_crafted_item()
        return self.notice("Lost the crafted item; its slot is free again.")

    def gain_corruption(self, amount: int) -> str:
        return self.take_corruption(amount, f"Gained {amount} Corruption.")

    def avoid_strain(self, amount: int) -> str:
        """Strain avoided on a task costs as much Corruption, as Oldheart has it."""
        change = f"Avoided {amount} strain on a task: gained {amount} Corruption."
        return self.take_corruption(amount, change)

    def take_corruption(self, amount: int, change: str) -> str:
        with self.undoable("Corruption gain"):
            check = self.session.add_corruption(amount, rng=self.rng)
        return self.notice(f"{change} {check_summary(check)}")

    def add_manifestation(self) -> str:
        with self.undoable("manifestation change"):
            self.session.add_manifestation()
        return self.notice("Manifestation added by hand.")

    def remove_manifestation(self) -> str:
        with self.undoable("manifestation change"):
            self.session.remove_manifestation()
        return self.notice("Manifestation removed by hand.")

    def set_standing(self, standing: int) -> str:
        # Clicking the dot already chosen moves nothing, so there is nothing to log or undo.
        if standing == self.session.standing:
            return ""
        with self.undoable("Standing change"):
            standing = self.session.set_standing(standing)
        return self.notice(standing_notice(standing))

    def new_character(self) -> str:
        """Start the sheet over in the same kit; history, notes and the file stay."""
        self.reset_sheet(self.session.profile_id)
        return self.notice("New character started.")

    def change_kit(self, genre: Genre) -> str:
        """A genre kit lasts a whole game, so changing it starts over: sheet, history and file."""
        self.reset_sheet(genre)
        self.history.clear()
        self.name = self.path = self.notes = ""
        self.saved_snapshot = None
        return f"New {PROFILES[genre].name} game started."

    def snapshot(self) -> dict[str, object]:
        """What a save keeps. The dice picked for a reroll or an item are left out: they are not
        worth a question."""
        return {
            **super().snapshot(),
            "session": self.session.model_dump(),
            "character": self.character,
            "draft": (
                self.tested_attribute,
                self.fear_level,
                self.assisted,
                self.expertise,
                self.power,
                self.target_standing,
            ),
        }

    def wrote_anything(self) -> bool:
        """Whether the player typed anything: the session name, notes, details or names."""
        session = self.session
        written = (
            *self.character.model_dump().values(),
            *session.bonuses.model_dump().values(),
            *session.power_names,
            *session.strain.names,
        )
        return super().wrote_anything() or any(written)

    def saved_session(self, name: str) -> SavedSession:
        return SavedSession(
            name=name,
            session=self.session.model_copy(deep=True),
            draft=self.draft_request(),
            notes=self.notes,
            character=self.character,
            history=tuple(self.history),
            reroll_indices=self.reroll_selection,
            item_target=self.item_target,
        )

    def parse_save(self, text: str) -> SavedSession:
        return parse_save(text, "player")

    def take_over(self, saved: SavedSession) -> None:
        """Replace this game with ``saved``: the sheet, history, name, notes and options."""
        super().take_over(saved)
        self.session = saved.session.model_copy(deep=True)
        self.character = saved.character
        draft = saved.draft
        self.tested_attribute = draft.attribute
        self.fear_level = draft.fear_level
        self.assisted = draft.assisted
        self.expertise = draft.expertise
        self.power = draft.power
        self.target_standing = draft.target_standing
        self.reroll_selection = saved.reroll_indices
        self.item_target = saved.item_target

    def options(self) -> tuple[Any, ...]:
        return (
            self.tested_attribute,
            self.assisted,
            self.expertise,
            self.power,
            self.target_standing,
            self.reroll_selection,
            self.item_target,
        )

    def restore_options(self, options: tuple[Any, ...]) -> None:
        (
            self.tested_attribute,
            self.assisted,
            self.expertise,
            self.power,
            self.target_standing,
            self.reroll_selection,
            self.item_target,
        ) = options

    def restore(self, state: RollSession, names: dict[NameSlot, str], action: str) -> None:
        shown = self.session.current_result
        for slot, name in names.items():
            RENAMERS[slot[0]](state, slot[1], name)
        self.session = state
        result = self.session.current_result
        # When the dice change back, the history shows them as they are again.
        if result is not None and result != shown:
            self.log_result(result, action, charged=False)
        else:
            self.notice(f"{action}.")

    def export_character(self) -> CharacterDetails:
        return self.character

    def sheet_lines(self) -> list[str]:
        return sheet_lines(self.session)
