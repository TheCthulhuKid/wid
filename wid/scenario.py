"""A scenario sheet: the GM's prep, from the pitch and the lists to the Dangers it brings."""

from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from wid.dangers import (
    Danger,
    DangerClass,
    DangerId,
    Difficulty,
    Replaceable,
    dangers_in_kit,
    require_fits,
    require_own_ids,
)
from wid.profiles import Genre
from wid.rolls import Standing

ENTRIES = 6
INCITEMENTS = 3
SCENARIO_DANGERS_MAX = 6

Entries = Annotated[tuple[str, ...], Field(min_length=ENTRIES, max_length=ENTRIES)]
BLANK_ENTRIES = ("",) * ENTRIES
Incitement = Annotated[tuple[str, ...], Field(min_length=INCITEMENTS, max_length=INCITEMENTS)]

type ScenarioText = Literal["title", "author", "pitch", "cast", "themes", "notes"]
type DangerText = Literal["name", "description", "notes"]
SCENARIO_TEXTS: tuple[ScenarioText, ...] = get_args(ScenarioText.__value__)
DANGER_TEXTS: tuple[DangerText, ...] = get_args(DangerText.__value__)
type TypedSlot = tuple[str | int, ...]


class Slot(StrEnum):
    """What a ``TypedSlot`` starts with: (TEXT, field), (INCITEMENT, row), (DANGER, id, field),
    (SCENE_DANGER, id) or (SCENE_NOTES,); a list's slot starts with the list instead."""

    TEXT = "text"
    INCITEMENT = "incitement"
    DANGER = "danger"
    SCENE_DANGER = "scene"
    SCENE_NOTES = "scene-notes"


class ScenarioList(StrEnum):
    """The sheet's four lists of six, each rolled on with 1d6; the value is its field."""

    SCENE_STARTERS = "scene_starters"
    NPCS = "npcs"
    WAYPOINTS = "waypoints"
    OBSTACLES = "obstacles"


type RollOn = ScenarioList | Literal[Slot.INCITEMENT]


class ScenarioDanger(Danger):
    description: str = ""
    notes: str = ""

    def in_scene(self) -> Danger:
        """The Danger as a scene holds it, without the sheet's text."""
        return Danger.model_validate(self.model_dump(include=set(Danger.model_fields)))


class Scenario(Replaceable):
    """The whole sheet. Its Dangers are numbered by its own counter, as a scene numbers its."""

    title: str = ""
    author: str = ""
    pitch: str = ""
    cast: str = ""
    themes: str = ""
    scene_starters: Entries = BLANK_ENTRIES
    npcs: Entries = BLANK_ENTRIES
    waypoints: Entries = BLANK_ENTRIES
    obstacles: Entries = BLANK_ENTRIES
    # The incitement table's rows, for 1–2, 3–4 and 5–6.
    incitement: Incitement = ("",) * INCITEMENTS
    dangers: tuple[ScenarioDanger, ...] = Field(default=(), max_length=SCENARIO_DANGERS_MAX)
    next_id: DangerId = 0
    notes: str = ""

    @model_validator(mode="after")
    def _own_ids(self) -> Self:
        require_own_ids(self.dangers, self.next_id)
        return self

    def with_danger(self, danger: ScenarioDanger, genre: Genre) -> Self:
        """The scenario with ``danger`` added under the next id; refused when ``genre`` lacks
        its class or standing."""
        require_fits(danger, genre)
        if len(self.dangers) >= SCENARIO_DANGERS_MAX:
            raise ValueError(f"A scenario holds up to {SCENARIO_DANGERS_MAX} Dangers.")
        added = danger.replace(id=self.next_id)
        return self.replace(dangers=(*self.dangers, added), next_id=self.next_id + 1)

    def replaced_by(self, sheet: Self, genre: Genre) -> Self:
        """``sheet`` in this scenario's place. Its Dangers are numbered on from this one's, so
        a scene never takes a new Danger for the one it started from; one ``genre`` cannot
        hold is refused by name."""
        scenario = sheet.replace(dangers=(), next_id=self.next_id)
        for danger in sheet.dangers:
            try:
                scenario = scenario.with_danger(danger, genre)
            except ValueError as error:
                raise ValueError(f"{sheet.title}, {danger.name}: {error}") from None
        return scenario

    def danger_at(self, index: int) -> ScenarioDanger:
        if not 0 <= index < len(self.dangers):
            raise ValueError("No such Danger.")
        return self.dangers[index]

    def changed_danger(
        self,
        index: int,
        danger_class: DangerClass,
        difficulty: Difficulty,
        standing: Standing | None,
        genre: Genre,
    ) -> Self:
        """The Danger at ``index`` with a new class, difficulty and standing; its id, name,
        description and notes stay."""
        danger = self.danger_at(index).replace(
            danger_class=danger_class, difficulty=difficulty, standing=standing
        )
        require_fits(danger, genre)
        return self.replace(dangers=(*self.dangers[:index], danger, *self.dangers[index + 1 :]))

    def entry(self, kind: RollOn, die: int) -> str:
        """What ``die`` lands on in a list, or in the incitement table's rows of two."""
        if kind == Slot.INCITEMENT:
            return self.incitement[(die - 1) // 2]
        return getattr(self, kind)[die - 1]

    def without(self, index: int) -> Self:
        self.danger_at(index)
        return self.replace(dangers=self.dangers[:index] + self.dangers[index + 1 :])

    def typed(self) -> dict[TypedSlot, str]:
        """Everything the GM types into the sheet, by slot, so an undo can keep it."""
        return {
            **{(Slot.TEXT, field): getattr(self, field) for field in SCENARIO_TEXTS},
            **{
                (kind.value, index): entry
                for kind in ScenarioList
                for index, entry in enumerate(getattr(self, kind))
            },
            **{(Slot.INCITEMENT, row): text for row, text in enumerate(self.incitement)},
            **{
                (Slot.DANGER, danger.id, field): getattr(danger, field)
                for danger in self.dangers
                for field in DANGER_TEXTS
            },
        }

    def with_typed(self, typed: dict[TypedSlot, str]) -> Self:
        """The scenario with ``typed`` written into its slots; slots it lacks are ignored."""
        texts = {
            field: typed.get((Slot.TEXT, field), getattr(self, field)) for field in SCENARIO_TEXTS
        }
        lists = {
            kind.value: tuple(
                typed.get((kind.value, index), entry)
                for index, entry in enumerate(getattr(self, kind))
            )
            for kind in ScenarioList
        }
        incitement = tuple(
            typed.get((Slot.INCITEMENT, row), text) for row, text in enumerate(self.incitement)
        )
        dangers = tuple(
            danger.replace(
                **{
                    field: typed.get((Slot.DANGER, danger.id, field), getattr(danger, field))
                    for field in DANGER_TEXTS
                }
            )
            for danger in self.dangers
        )
        return self.replace(**texts, **lists, incitement=incitement, dangers=dangers)

    def in_kit(self, genre: Genre) -> tuple[Self, list[str]]:
        """The scenario as ``genre`` can hold it, and the labels of the Dangers dropped."""
        kept, dropped = dangers_in_kit(self.dangers, genre)
        return self.replace(dangers=kept), dropped

    def fits(self, genre: Genre) -> bool:
        return self.in_kit(genre) == (self, [])
