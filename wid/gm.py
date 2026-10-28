"""The Game Master's sitting: the genre kit and the scene, with an action for each control.

Like ``Game``, each action returns the feedback to show and refuses with ``ValueError``. An
activation changes nothing, so like **Roll 1d6** it is logged and not undone; a clash moves the
threshold, so it is undoable like a player's roll, and taking it back gives no die back.
"""

from pathlib import Path
from random import Random
from typing import Any

from wid.dangers import (
    DANGERS_MAX,
    Activation,
    Danger,
    DangerClass,
    Difficulty,
    Scene,
    activate,
    classes_for,
)
from wid.formatting import activation_line, danger_summary, scene_summary
from wid.game import BaseGame
from wid.profiles import PROFILES, Genre, WiDProfile
from wid.rolls import roll_d6
from wid.sessions import GmSave, parse_save


class GmGame(BaseGame):
    def __init__(self, *, rng: Random | None = None, recovery_path: Path | None = None):
        super().__init__(rng=rng, recovery_path=recovery_path)
        self.genre = Genre.CORE
        self.scene = Scene()
        # Shown on screen until the next activation; the history keeps it, the save does not.
        self.last_activation: Activation | None = None

    @property
    def state(self) -> Scene:
        return self.scene

    @property
    def in_play(self) -> bool:
        return bool(self.scene.dangers)

    @property
    def profile(self) -> WiDProfile:
        return PROFILES[self.genre]

    def typed_names(self, state: Scene) -> dict[int, str]:
        return {index: danger.name for index, danger in enumerate(state.dangers)}

    def restore(self, state: Scene, names: dict[int, str], action: str) -> None:
        for index, name in names.items():
            state = state.rename(index, name)
        self.scene = state
        self.notice(f"{action}.")

    def options(self) -> tuple[Any, ...]:
        return (self.genre,)

    def restore_options(self, options: tuple[Any, ...]) -> None:
        (self.genre,) = options

    def snapshot(self) -> dict[str, object]:
        return {**super().snapshot(), "genre": self.genre, "scene": self.scene.model_dump()}

    def wrote_anything(self) -> bool:
        """Whether the GM typed anything: the session name, notes or a Danger's name."""
        return super().wrote_anything() or any(danger.name for danger in self.scene.dangers)

    def saved_session(self, name: str) -> GmSave:
        return GmSave(
            name=name,
            genre=self.genre,
            scene=self.scene,
            notes=self.notes,
            history=tuple(self.history),
        )

    def parse_save(self, text: str) -> GmSave:
        return parse_save(text, "gm")

    def take_over(self, saved: GmSave) -> None:
        super().take_over(saved)
        self.genre = saved.genre
        self.scene = saved.scene
        self.last_activation = None

    def sheet_lines(self) -> list[str]:
        """The kit, the PC count, each Danger and the scene; an empty scene has no scene line."""
        scene = self.scene
        lines = [f"Kit: {self.profile.name}", f"PCs: {scene.pc_count}"]
        lines += [
            danger_summary(danger, index, scene.pc_count)
            for index, danger in enumerate(scene.dangers)
        ]
        if scene.dangers:
            lines.append(scene_summary(scene))
        return lines

    def set_pc_count(self, pc_count: int) -> str:
        if pc_count == self.scene.pc_count:
            return ""
        with self.undoable("PC count change"):
            self.scene = self.scene.with_pc_count(pc_count)
        return self.notice(f"PCs: {pc_count}.")

    def add_danger(self, name: str, danger_class: DangerClass, difficulty: Difficulty) -> str:
        if danger_class not in classes_for(self.genre):
            raise ValueError(f"{self.profile.name} has no {danger_class.label}s.")
        if len(self.scene.dangers) >= DANGERS_MAX:
            raise ValueError(f"A scene holds up to {DANGERS_MAX} Dangers.")
        danger = Danger(name=name, danger_class=danger_class, difficulty=difficulty)
        with self.undoable("Danger added"):
            self.scene = self.scene.replace(dangers=(*self.scene.dangers, danger))
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
        if amount < 1:
            raise ValueError("Raise the threshold by at least 1.")
        with self.undoable("threshold raise"):
            self.scene = self.scene.raise_threshold(amount)
        return self.notice(f"Threshold raised by {amount}. {self.summary()}")

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

    def keep_scene(self, genre: Genre) -> str:
        """Change kit and keep the scene, less the Dangers of a class the new kit lacks."""
        if genre == self.genre:
            return ""
        with self.undoable("kit change", options=True):
            self.scene, dropped = self.scene.in_kit(genre)
            self.genre = genre
        text = f"Kit changed to {self.profile.name}."
        if dropped:
            text += f" Dropped {', '.join(dropped)}."
        return self.notice(text)

    def start_new(self, genre: Genre) -> str:
        """Start over in ``genre`` with an empty scene; history, notes and the file go too."""
        self.genre = genre
        self.scene = Scene()
        self.last_activation = None
        self.history.clear()
        self.name = self.path = self.notes = ""
        self.saved_snapshot = None
        self.undo_stack = []
        return f"New {self.profile.name} GM game started."

    def require_dangers(self) -> None:
        if not self.scene.dangers:
            raise ValueError("Add a Danger first.")

    def summary(self) -> str:
        return scene_summary(self.scene)
