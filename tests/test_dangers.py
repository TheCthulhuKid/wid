import pytest
from helpers import ScriptedRandom

from wid.dangers import Ability, Danger, DangerClass, Difficulty, Scene, activate, classes_for
from wid.formatting import (
    NO_DANGER_HINT,
    activation_line,
    danger_summary,
    loadout_rows,
    scene_summary,
)
from wid.profiles import Genre

BRUTE = Danger(danger_class=DangerClass.BRUTE, difficulty=Difficulty.COMPETENT)
TITAN = Danger(name="Zeus", danger_class=DangerClass.TITAN, difficulty=Difficulty.MEGA)


def test_danger_numbers_and_loadout():
    assert BRUTE.threshold(4) == 8
    assert BRUTE.hits_to_pass == 1
    assert BRUTE.loadout == (
        Ability.HARASS,
        Ability.SCARE,
        Ability.KILL,
        Ability.KILL,
        Ability.KILL,
        Ability.HARASS,
    )
    assert BRUTE.label(0) == "Danger 1"
    assert danger_summary(BRUTE, 0, 4) == "Danger 1: Competent Brute — threshold 8, 1 hit to pass"

    assert TITAN.threshold(3) == 12
    assert TITAN.hits_to_pass == 2
    assert TITAN.loadout[3:] == (Ability.DOMINATE, Ability.DOMINATE, Ability.KILL)
    assert Danger(danger_class=DangerClass.BRUTE, difficulty=Difficulty.PETTY).threshold(3) == 4

    assert classes_for(Genre.CORE) == (
        DangerClass.BRUTE,
        DangerClass.SWARM,
        DangerClass.NIGHTMARE,
        DangerClass.DISASTER,
    )
    assert classes_for(Genre.HECKBOY)[-1] == DangerClass.TITAN
    rows = loadout_rows(TITAN.loadout, Genre.HECKBOY)
    assert rows[3] == ("4", "Dominate", "PC(s) with highest scared", "Ferocity")
    assert rows[5] == ("6", "Kill", "PC(s) with most wounds", "Savvy")


def test_scene_combines_its_dangers():
    assert scene_summary(Scene()) == NO_DANGER_HINT
    scene = Scene(pc_count=3, dangers=(BRUTE, TITAN), hostile=True).raise_threshold(2)
    assert scene.threshold == 6 + 12 + 2
    assert scene.strongest == TITAN
    assert scene.loadout == TITAN.loadout
    assert scene.hits_to_pass == 2
    assert scene_summary(scene) == (
        "Threshold 20 (raised 2), progress 0 — 2 hits to pass. Dangers fight each other"
    )

    committed = scene.commit(25)
    assert committed.progress == 20
    assert committed.overcome
    assert scene_summary(committed).endswith("— 2 hits to pass. Overcome. Dangers fight each other")

    removed = committed.without(1)
    assert removed.dangers == (BRUTE,)
    assert removed.threshold == 8
    assert removed.progress == 8
    with pytest.raises(ValueError):
        committed.without(2)
    with pytest.raises(ValueError):
        Scene(dangers=(BRUTE,), progress=9)

    core, dropped = committed.in_kit(Genre.CORE)
    assert core.dangers == (BRUTE,)
    assert dropped == ["Zeus"]
    assert committed.in_kit(Genre.HECKBOY) == (committed, [])


def test_activation_uses_the_kits_attributes():
    scene = Scene(dangers=(TITAN,))
    activation = activate(scene, Genre.HECKBOY, ScriptedRandom([4, 2, 5]))
    assert activation.ability == Ability.DOMINATE
    assert activation.target == "PC who acted most recently"
    assert activation.attribute == "Savvy"
    assert activation_line(activation) == (
        "Activation (4, 2, 5): Dominate — PC who acted most recently, defending with Savvy"
    )
    with pytest.raises(ValueError):
        activate(Scene(), Genre.HECKBOY, ScriptedRandom([1, 1, 1]))
