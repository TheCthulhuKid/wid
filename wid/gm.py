"""The Game Master's sitting: the genre kit, the scenario and the scene, with an action for
each control.

Like ``Game``, each action returns the feedback to show and refuses with ``ValueError``. An
activation changes nothing, so like **Roll 1d6** it is logged and not undone; a clash moves the
threshold, so it is undoable like a player's roll, and taking it back gives no die back.
"""

from pathlib import Path
from random import Random
from typing import Any

from wid.base_game import BaseGame, reported
from wid.dangers import (
    Activation,
    Complexity,
    Danger,
    DangerClass,
    Difficulty,
    Scene,
    SceneEnd,
    Standing,
    activate,
)
from wid.formatting import (
    acting_notice,
    activation_line,
    barricade_text,
    danger_kind,
    danger_summary,
    one_line,
    revelations_line,
    roll_on_line,
    scenario_line,
    scene_record,
    scene_summary,
    task_strain_line,
)
from wid.profiles import PROFILES, Genre, WiDProfile
from wid.rolls import FrozenModel, roll_d6
from wid.scenario import (
    RollOn,
    Scenario,
    ScenarioDanger,
    Slot,
    TypedSlot,
)
from wid.scenario_sheet import chosen_sheet, write_sheet
from wid.sessions import GmSave, parse_save, session_file_path
from wid.storage import write_text


class GmState(FrozenModel):
    """What Undo copies and puts back: a change to either is taken back whole."""

    scene: Scene
    scenario: Scenario


class GmGame(BaseGame):
    def __init__(self, *, rng: Random | None = None, recovery_path: Path | None = None):
        super().__init__(rng=rng, recovery_path=recovery_path)
        self.genre = Genre.CORE
        self.scene = Scene()
        self.scenario = Scenario()
        # Shown on screen until the next activation; the history keeps it, the save does not.
        self.last_activation: Activation | None = None

    @property
    def state(self) -> GmState:
        return GmState(scene=self.scene, scenario=self.scenario)

    @property
    def in_play(self) -> bool:
        return bool(self.scene.dangers or self.scenario.dangers)

    @property
    def profile(self) -> WiDProfile:
        return PROFILES[self.genre]

    @property
    def scene_from_scenario(self) -> ScenarioDanger | None:
        """The scenario Danger the scene was started from, unless the GM has since removed it."""
        danger_id = self.scene.scenario_danger_id
        return next((danger for danger in self.scenario.dangers if danger.id == danger_id), None)

    def typed_names(self, state: GmState) -> dict[TypedSlot, str]:
        """The scene's Danger names and notes, and the scenario's typed text."""
        names = {(Slot.SCENE_DANGER, danger.id): danger.name for danger in state.scene.dangers}
        return {**names, (Slot.SCENE_NOTES,): state.scene.notes, **state.scenario.typed()}

    def restore(self, state: GmState, names: dict[TypedSlot, str], action: str) -> None:
        dangers = tuple(
            danger.replace(name=names.get((Slot.SCENE_DANGER, danger.id), danger.name))
            for danger in state.scene.dangers
        )
        notes = names.get((Slot.SCENE_NOTES,), state.scene.notes)
        self.scene = state.scene.replace(dangers=dangers, notes=notes)
        self.scenario = state.scenario.with_typed(names)
        self.notice(f"{action}.")

    def options(self) -> tuple[Any, ...]:
        return (self.genre,)

    def restore_options(self, options: tuple[Any, ...]) -> None:
        (self.genre,) = options

    def snapshot(self) -> dict[str, object]:
        return {
            **super().snapshot(),
            "genre": self.genre,
            "scene": self.scene.model_dump(),
            "scenario": self.scenario.model_dump(),
        }

    def wrote_anything(self) -> bool:
        """Whether the GM typed anything: the session name, notes, the scene or the scenario."""
        typed = self.typed_names(self.state).values()
        return super().wrote_anything() or any(typed)

    def saved_session(self, name: str) -> GmSave:
        return GmSave(
            name=name,
            genre=self.genre,
            scene=self.scene,
            scenario=self.scenario,
            notes=self.notes,
            history=tuple(self.history),
        )

    def parse_save(self, text: str) -> GmSave:
        return parse_save(text, "gm")

    def take_over(self, saved: GmSave) -> None:
        super().take_over(saved)
        self.genre = saved.genre
        self.scene = saved.scene
        self.scenario = saved.scenario
        self.last_activation = None

    def sheet_lines(self) -> list[str]:
        """The kit, the scenario, the PC count, each Danger and the scene; an empty scenario or
        scene has no line."""
        scene = self.scene
        lines = [f"Kit: {self.profile.name}"]
        if self.scenario != Scenario():
            lines.append(scenario_line(self.scenario))
        lines.append(f"PCs: {scene.pc_count}")
        lines += [
            danger_summary(danger, index, scene.pc_count)
            for index, danger in enumerate(scene.dangers)
        ]
        if scene.dangers:
            lines.append(scene_summary(scene))
        if self.profile.has_revelations:
            lines.append(revelations_line(scene))
        return lines

    def set_pc_count(self, pc_count: int) -> str:
        if pc_count == self.scene.pc_count:
            return ""
        with self.undoable("PC count change"):
            self.scene = self.scene.with_pc_count(pc_count)
        return self.notice(f"PCs: {pc_count}.")

    def add_danger(
        self,
        name: str,
        danger_class: DangerClass,
        difficulty: Difficulty,
        standing: Standing | None = None,
    ) -> str:
        """Add a Danger; ``standing`` is Ball Season's, and refused elsewhere."""
        danger = Danger(
            name=name, danger_class=danger_class, difficulty=difficulty, standing=standing
        )
        with self.undoable("Danger added"):
            self.scene = self.scene.with_danger(danger, self.genre)
        index = len(self.scene.dangers) - 1
        return self.notice(f"Added {danger_summary(danger, index, self.scene.pc_count)}")

    def rename_danger(self, index: int, name: str) -> None:
        """Name a Danger; nothing is logged, and the name stays across an undo."""
        self.scene = self.scene.rename(index, name)

    def remove_danger(self, index: int) -> str:
        label = self.scene.danger_at(index).label(index)
        with self.undoable("Danger removed"):
            self.scene = self.scene.without(index)
        return self.notice(f"Removed {label}.")

    def commit_hits(self, hits: int) -> str:
        self.require_dangers()
        if hits < 1:
            raise ValueError("Commit at least 1 hit.")
        with self.undoable("hits committed"):
            self.scene = self.scene.commit(hits)
        return self.notice(f"Committed {hits} {'hit' if hits == 1 else 'hits'}. {self.summary()}")

    def raise_threshold(self, amount: int) -> str:
        self.require_dangers()
        if amount < 1:
            raise ValueError("Raise the threshold by at least 1.")
        with self.undoable("threshold raise"):
            self.scene = self.scene.raise_threshold(amount)
        return self.notice(f"Threshold raised by {amount}. {self.summary()}")

    def choose_acting(self, index: int | None) -> str:
        """Roll on the Danger at ``index`` from now on, or on the strongest for None."""
        chosen = self.scene.with_acting(index)
        if chosen == self.scene:
            return ""
        with self.undoable("acting Danger choice"):
            self.scene = chosen
        return self.notice(acting_notice(self.scene))

    def set_hostile(self, hostile: bool) -> str:
        if hostile == self.scene.hostile:
            return ""
        with self.undoable("hostility change"):
            self.scene = self.scene.replace(hostile=hostile)
        return self.notice(f"Dangers {'now' if hostile else 'no longer'} fight each other.")

    def activate(self) -> str:
        self.last_activation = activate(self.scene, self.genre, self.rng)
        return self.notice(activation_line(self.last_activation))

    def clash(self) -> str:
        """Hostile Dangers harm each other at the end of a round: 1d6 off the threshold."""
        self.require_dangers()
        if not self.scene.hostile:
            raise ValueError("The Dangers are not fighting each other.")
        with self.undoable("clash"):
            die = roll_d6(self.rng)
            self.scene = self.scene.commit(die)
        return self.notice(f"Dangers clash: rolled {die}. {self.summary()}")

    def task_strain(self, complexity: Complexity, mismatched: int = 0) -> str:
        """Log the strain a task taxes the PCs; it changes nothing in the scene.

        In Ball Season, ``mismatched`` PCs of another standing than the task's add 1 each.
        """
        if mismatched and not self.profile.has_standing:
            raise ValueError(f"{self.profile.name} has no Standing.")
        if not 0 <= mismatched <= self.scene.pc_count:
            raise ValueError("No more PCs can be of another standing than there are PCs.")
        return self.notice(task_strain_line(complexity, self.scene.pc_count, mismatched))

    def move_barricade(self, step: int) -> str:
        with self.undoable("barricade change"):
            self.scene = self.scene.move_barricade(step, self.genre)
        return self.notice(f"Barricade {step:+d}: {barricade_text(self.scene.barricade).lower()}.")

    def spend_hits(self, hits: int) -> str:
        """Hits spent on an investigation advance the revelations track by one each."""
        if hits < 1:
            raise ValueError("Spend at least 1 hit.")
        return self.advance_revelations(f"Hits spent: {hits}", hits)

    def task_done(self, complexity: Complexity) -> str:
        advance = complexity.revelation_advance
        return self.advance_revelations(f"{complexity.label} task done: +{advance}", advance)

    def advance_revelations(self, change: str, amount: int) -> str:
        revealed = self.scene.revealed
        with self.undoable("revelations advance"):
            self.scene = self.scene.advance_revelations(amount, self.genre)
        text = f"{change}. {revelations_line(self.scene)}."
        if self.scene.revealed > revealed:
            text += " A revelation!"
        return self.notice(text)

    def set_revelations(self, count: int) -> str:
        if count == self.scene.revelations:
            return ""
        with self.undoable("revelations change"):
            self.scene = self.scene.with_revelations(count, self.genre)
        return self.notice(f"Revelations to find: {count}. {revelations_line(self.scene)}.")

    def keep_scene(self, genre: Genre) -> str:
        """Change kit and keep the scene and the scenario, less the Dangers of a class the new
        kit lacks."""
        if genre == self.genre:
            return ""
        with self.undoable("kit change", options=True):
            self.scene, dropped = self.scene.in_kit(genre)
            self.scenario, dropped_from_scenario = self.scenario.in_kit(genre)
            self.genre = genre
        text = f"Kit changed to {self.profile.name}."
        if dropped:
            text += f" Dropped {', '.join(dropped)}."
        if dropped_from_scenario:
            text += f" Dropped {', '.join(dropped_from_scenario)} from the scenario."
        return self.notice(text)

    def start_new(self, genre: Genre) -> str:
        """Start over in ``genre`` with an empty scene; history, notes and the file go too."""
        self.genre = genre
        self.scene = Scene()
        self.scenario = Scenario()
        self.last_activation = None
        self.start_over()
        return f"New {self.profile.name} GM game started."

    def type_into_scenario(self, typed: dict[TypedSlot, str]) -> None:
        """Typed text is the GM's: nothing is logged, and it stays across an undo."""
        self.scenario = self.scenario.with_typed(typed)

    def add_scenario_danger(
        self,
        name: str,
        danger_class: DangerClass,
        difficulty: Difficulty,
        standing: Standing | None = None,
    ) -> str:
        danger = ScenarioDanger(
            name=name, danger_class=danger_class, difficulty=difficulty, standing=standing
        )
        with self.undoable("scenario Danger added"):
            self.scenario = self.scenario.with_danger(danger, self.genre)
        label = danger.label(len(self.scenario.dangers) - 1)
        return self.notice(f"Added {label} to the scenario.")

    def change_scenario_danger(
        self,
        index: int,
        danger_class: DangerClass,
        difficulty: Difficulty,
        standing: Standing | None = None,
    ) -> str:
        changed = self.scenario.changed_danger(
            index, danger_class, difficulty, standing, self.genre
        )
        if changed == self.scenario:
            return ""
        with self.undoable("scenario Danger change"):
            self.scenario = changed
        danger = changed.dangers[index]
        return self.notice(f"Changed {danger.label(index)} to {danger_kind(danger)}.")

    def remove_scenario_danger(self, index: int) -> str:
        label = self.scenario.danger_at(index).label(index)
        with self.undoable("scenario Danger removed"):
            self.scenario = self.scenario.without(index)
        return self.notice(f"Removed {label} from the scenario.")

    def clear_scenario(self) -> str:
        if self.scenario == Scenario():
            return ""
        with self.undoable("scenario cleared"):
            self.scenario = Scenario()
        return self.notice("Scenario cleared.")

    def import_scenario(self, text: str, choice: int | None = None) -> str:
        """Replace the scenario with one read from a sheet; with several, ``choice`` says which,
        and without it ``ChooseScenario`` names them."""
        sheet = chosen_sheet(text, choice)
        scenario = self.scenario.replaced_by(sheet, self.genre)
        with self.undoable("scenario import"):
            self.scenario = scenario
        return self.notice(f"Imported the scenario {one_line(sheet.title)}.")

    def import_scenario_file(self, text: str, choice: int | None = None) -> str:
        with reported("import scenario"):
            path = session_file_path(text, label="scenario file")
            return self.import_scenario(path.read_text(encoding="utf-8"), choice)

    def scenario_text(self) -> str:
        """The scenario as a sheet, for an export."""
        if self.scenario == Scenario():
            raise ValueError("The scenario is empty: write or import one first.")
        return write_sheet(self.scenario, self.genre)

    def export_scenario(self, text: str, *, overwrite: bool = False) -> str:
        sheet = self.scenario_text()
        with reported("export scenario"):
            path = session_file_path(text, label="scenario file")
            write_text(path, sheet, overwrite=overwrite)
        return f"Exported the scenario to {path}."

    def type_scene_notes(self, notes: str) -> None:
        """Typed text is the GM's: nothing is logged, and it stays across an undo."""
        self.scene = self.scene.replace(notes=notes)

    def start_scene(self, index: int) -> str:
        """Start a scene with the scenario Danger at ``index``; the last one must end first."""
        if self.scene.dangers:
            raise ValueError("End this scene first.")
        danger = self.scenario.danger_at(index)
        with self.undoable("scene start"):
            self.scene = self.scene.starting(danger.in_scene(), self.genre, danger.id)
        return self.notice(f"Scene started: {danger.label(index)}.")

    def end_scene(self) -> str:
        if not self.scene.overcome:
            raise ValueError("Overcome the scene before ending it.")
        return self.close_scene(SceneEnd.ENDED)

    def lose_scene(self) -> str:
        self.require_dangers()
        if self.scene.overcome:
            raise ValueError("The scene is overcome: end it instead.")
        return self.close_scene(SceneEnd.LOST)

    def close_scene(self, end: SceneEnd) -> str:
        """Record the scene and its notes in the history and empty it; the feedback leaves the
        notes out."""
        record = scene_record(self.scene, end)
        with self.undoable(f"{end} scene"):
            self.scene = self.scene.cleared()
        self.last_activation = None
        self.notice(record)
        return record.splitlines()[0]

    def roll_on(self, kind: RollOn) -> str:
        die = roll_d6(self.rng)
        return self.notice(roll_on_line(kind, die, self.scenario.entry(kind, die)))

    def require_dangers(self) -> None:
        if not self.scene.dangers:
            raise ValueError("Add a Danger first.")

    def summary(self) -> str:
        return scene_summary(self.scene)
