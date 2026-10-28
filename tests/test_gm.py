import pytest
from helpers import ScriptedRandom

from wid.dangers import DangerClass, Difficulty
from wid.gm import GmGame
from wid.profiles import Genre


def heckboy_scene() -> GmGame:
    game = GmGame(rng=ScriptedRandom([4, 2, 5, 3]))
    game.start_new(Genre.HECKBOY)
    game.add_danger("", DangerClass.BRUTE, Difficulty.COMPETENT)
    game.add_danger("Zeus", DangerClass.TITAN, Difficulty.MEGA)
    return game


def test_a_scene_is_built_committed_undone_and_saved(tmp_path):
    game = heckboy_scene()
    assert game.history[-1].notice == "Added Zeus: Mega Titan — threshold 16, 2 hits to pass"
    assert game.set_pc_count(3) == "PCs: 3."
    assert game.commit_hits(5) == "Committed 5 hits. Threshold 18, progress 5 — 2 hits to pass"
    assert game.activate() == (
        "Activation (4, 2, 5): Dominate — PC who acted most recently, defending with Savvy"
    )
    with pytest.raises(ValueError, match="not fighting each other"):
        game.clash()
    game.set_hostile(True)
    assert game.clash().startswith("Dangers clash: rolled 3. Threshold 18, progress 8")
    with pytest.raises(ValueError, match="has no Schemers"):
        game.add_danger("", DangerClass.SCHEMER, Difficulty.PETTY)

    game.rename_danger(0, "Bear")
    assert game.undo() == "Undid the last clash."
    scene = game.scene
    assert (scene.hostile, scene.progress, scene.dangers[0].name) == (True, 5, "Bear")

    game.recovery_path = tmp_path / "gm-recovery.json"
    assert game.keep_recovery() == ""
    recovered = GmGame(recovery_path=game.recovery_path)
    recovered.restore_recovery()
    assert (recovered.genre, recovered.scene) == (game.genre, game.scene)

    game.name, game.path = "Friday", str(tmp_path / "gm.json")
    game.save()
    assert not game.has_unsaved_state()
    loaded = GmGame()
    saved, path = loaded.read_save(game.path)
    assert loaded.load(saved, path) == f"Loaded Friday from {game.path}."
    assert (loaded.genre, loaded.scene, loaded.history) == (game.genre, game.scene, game.history)
    assert "- Bear: Competent Brute — threshold 6, 1 hit to pass" in loaded.history_text()
    assert loaded.history_text().count("Character:") == 0


def test_keep_scene_drops_what_the_kit_lacks_then_start_new():
    game = heckboy_scene()
    assert game.keep_scene(Genre.CORE) == "Kit changed to Core WiD. Dropped Zeus."
    assert (game.genre, len(game.scene.dangers)) == (Genre.CORE, 1)
    game.undo()
    assert (game.genre, len(game.scene.dangers)) == (Genre.HECKBOY, 2)
    assert game.start_new(Genre.OLDHEART) == "New Oldheart GM game started."
    assert (game.genre, game.scene.dangers, game.history, game.can_undo) == (
        Genre.OLDHEART,
        (),
        [],
        False,
    )
    assert game.sheet_lines() == [
        "Kit: Oldheart",
        "PCs: 4",
        "Revelations: 0 of 12 advanced, 0 of 3 revealed",
    ]
