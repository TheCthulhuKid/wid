import pytest
from helpers import ScriptedRandom

from wid.dangers import (
    Ability,
    Complexity,
    Danger,
    DangerClass,
    Difficulty,
    Scene,
    Standing,
    activate,
    classes_for,
)
from wid.formatting import (
    NO_DANGER_HINT,
    activation_line,
    danger_summary,
    loadout_rows,
    revelations_line,
    scene_summary,
    task_strain_line,
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
    assert [complexity.strain_total(3) for complexity in Complexity] == [3, 6, 9]
    assert task_strain_line(Complexity.MEDIUM, 4) == "Medium task: 8 strain for 4 PCs to share."

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

    assert committed.with_pc_count(1).progress == committed.with_pc_count(1).threshold == 8
    assert committed.rename(1, "Jupiter").dangers[1].name == "Jupiter"
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


def test_each_kits_scene_tracker_counts_and_is_refused_elsewhere():
    schemer = Danger(danger_class=DangerClass.SCHEMER, difficulty=Difficulty.BOSS)
    esteemed = schemer.replace(standing=Standing.ESTEEMED)
    scene = Scene(pc_count=2).with_danger(esteemed, Genre.BALL_SEASON)
    assert danger_summary(esteemed, 0, 2) == (
        "Danger 1: Boss Schemer, Esteemed — threshold 6, 2 hits to pass"
    )
    activation = activate(scene, Genre.BALL_SEASON, ScriptedRandom([1, 1, 1]))
    assert activation_line(activation).endswith("defending with Propriety; the Danger is Esteemed")
    with pytest.raises(ValueError, match="Core WiD has no Standing"):
        Scene().with_danger(BRUTE.replace(standing=Standing.ESTEEMED), Genre.CORE)
    with pytest.raises(ValueError, match="Core WiD has no Schemers"):
        Scene().with_danger(schemer, Genre.CORE)

    walled = (
        Scene()
        .move_barricade(1, Genre.THIS_ISNT_HAPPENING)
        .move_barricade(1, Genre.THIS_ISNT_HAPPENING)
    )
    assert walled.barricade == 2
    assert scene_summary(walled.with_danger(BRUTE, Genre.CORE)).endswith("Barricade 2 of 6")
    with pytest.raises(ValueError, match="no barricade"):
        Scene().move_barricade(-1, Genre.THIS_ISNT_HAPPENING)
    with pytest.raises(ValueError, match="Core WiD has no barricade"):
        Scene().move_barricade(1, Genre.CORE)

    track = Scene().advance_revelations(Complexity.HIGH.revelation_advance, Genre.OLDHEART)
    track = track.advance_revelations(3, Genre.OLDHEART)
    assert (track.revelation_progress, track.revealed) == (7, 1)
    assert revelations_line(track) == "Revelations: 7 of 12 advanced, 1 of 3 revealed"
    assert track.advance_revelations(20, Genre.OLDHEART).revelation_progress == 12
    assert track.with_revelations(1, Genre.OLDHEART).revelation_progress == 4
    with pytest.raises(ValueError, match="Core WiD has no revelations track"):
        Scene().advance_revelations(1, Genre.CORE)

    # Another kit keeps none of them.
    everything = Scene(dangers=(esteemed,), barricade=3, revelation_progress=5)
    core, dropped = everything.in_kit(Genre.CORE)
    assert (core.dangers, core.barricade, core.revelation_progress, dropped) == (
        (),
        0,
        0,
        ["Danger 1"],
    )
    assert not everything.fits(Genre.BALL_SEASON) and everything.in_kit(Genre.BALL_SEASON)[0].fits(
        Genre.BALL_SEASON
    )


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
