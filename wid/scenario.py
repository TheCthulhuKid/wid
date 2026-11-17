"""A scenario sheet: the GM's prep, from the pitch and the lists to the Dangers it brings."""

from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from wid.dangers import (
    Count,
    Danger,
    DangerClass,
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
# A slot the GM types into: ("text", field), (list, entry), ("incitement", row) or
# ("danger", id, field).
type TypedSlot = tuple[str | int, ...]


class ScenarioList(StrEnum):
    """The sheet's four lists of six, each rolled on with 1d6; the value is its field."""

    SCENE_STARTERS = "scene_starters"
    NPCS = "npcs"
    WAYPOINTS = "waypoints"
    OBSTACLES = "obstacles"


class ScenarioDanger(Danger):
    description: str = ""
    notes: str = ""


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
    next_id: Count = 0
    notes: str = ""

    @model_validator(mode="after")
    def _own_ids(self) -> Self:
        require_own_ids(self.dangers, self.next_id)
        return self

    def with_text(self, field: ScenarioText, text: str) -> Self:
        return self.replace(**{field: text})

    def with_entry(self, kind: ScenarioList, index: int, text: str) -> Self:
        return self.replace(**{kind: put(getattr(self, kind), index, text, "No such entry.")})

    def with_incitement(self, row: int, text: str) -> Self:
        return self.replace(incitement=put(self.incitement, row, text, "No such incitement."))

    def with_danger(self, danger: ScenarioDanger, genre: Genre) -> Self:
        """The scenario with ``danger`` added under the next id; refused when ``genre`` lacks
        its class or standing."""
        require_fits(danger, genre)
        if len(self.dangers) >= SCENARIO_DANGERS_MAX:
            raise ValueError(f"A scenario holds up to {SCENARIO_DANGERS_MAX} Dangers.")
        added = danger.replace(id=self.next_id)
        return self.replace(dangers=(*self.dangers, added), next_id=self.next_id + 1)

    def danger_at(self, index: int) -> ScenarioDanger:
        if not 0 <= index < len(self.dangers):
            raise ValueError("No such Danger.")
        return self.dangers[index]

    def with_danger_text(self, index: int, field: DangerText, text: str) -> Self:
        danger = self.danger_at(index).replace(**{field: text})
        return self.replace(dangers=put(self.dangers, index, danger, "No such Danger."))

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
        return self.replace(dangers=put(self.dangers, index, danger, "No such Danger."))

    def without(self, index: int) -> Self:
        self.danger_at(index)
        return self.replace(dangers=self.dangers[:index] + self.dangers[index + 1 :])

    def typed(self) -> dict[TypedSlot, str]:
        """Everything the GM types into the sheet, by slot, so an undo can keep it."""
        return {
            **{("text", field): getattr(self, field) for field in SCENARIO_TEXTS},
            **{
                (kind.value, index): entry
                for kind in ScenarioList
                for index, entry in enumerate(getattr(self, kind))
            },
            **{("incitement", row): text for row, text in enumerate(self.incitement)},
            **{
                ("danger", danger.id, field): getattr(danger, field)
                for danger in self.dangers
                for field in DANGER_TEXTS
            },
        }

    def with_typed(self, typed: dict[TypedSlot, str]) -> Self:
        """The scenario with ``typed`` written into its slots; slots it lacks are ignored."""
        texts = {
            field: typed.get(("text", field), getattr(self, field)) for field in SCENARIO_TEXTS
        }
        lists = {
            kind.value: tuple(
                typed.get((kind.value, index), entry)
                for index, entry in enumerate(getattr(self, kind))
            )
            for kind in ScenarioList
        }
        incitement = tuple(
            typed.get(("incitement", row), text) for row, text in enumerate(self.incitement)
        )
        dangers = tuple(
            danger.replace(
                **{
                    field: typed.get(("danger", danger.id, field), getattr(danger, field))
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


def put[T](items: tuple[T, ...], index: int, item: T, missing: str) -> tuple[T, ...]:
    """``items`` with ``item`` at ``index``; an index outside them is refused with ``missing``."""
    if not 0 <= index < len(items):
        raise ValueError(missing)
    return (*items[:index], item, *items[index + 1 :])
