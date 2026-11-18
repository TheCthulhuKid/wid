import json

import pytest
from helpers import ScriptedRandom

from wid.dangers import DangerClass, Difficulty
from wid.gm import GmGame
from wid.profiles import Genre
from wid.rolls import Standing
from wid.scenario import ScenarioList, Slot
from wid.sessions import GmSave


def heckboy_scene() -> GmGame:
    game = GmGame(rng=ScriptedRandom([4, 2, 5, 3]))
    game.start_new(Genre.HECKBOY)
    game.add_danger("", DangerClass.BRUTE, Difficulty.HEAVY)
    game.add_danger("Zeus", DangerClass.TITAN, Difficulty.MEGA)
    return game


def test_a_scene_commits_activates_and_clashes():
    with pytest.raises(ValueError, match="Add a Danger first"):
        GmGame().raise_threshold(1)
    game = heckboy_scene()
    assert game.history[-1].notice == "Added Zeus: Mega Titan — threshold 16, 2 hits to pass"
    with pytest.raises(ValueError, match="has no Schemers"):
        game.add_danger("", DangerClass.SCHEMER, Difficulty.PETTY)
    assert game.set_pc_count(3) == "PCs: 3."
    assert game.commit_hits(5) == "Committed 5 hits. Threshold 18, progress 5 — 2 hits to pass"
    assert game.activate() == (
        "Zeus (Mega Titan) activates (4, 2, 5): Dominate — PC who acted most recently, "
        "defending with Savvy"
    )
    assert game.choose_acting(0) == "Acting Danger: Danger 1 (Heavy Brute)."
    assert game.choose_acting(0) == ""
    assert game.undo() == "Undid the last acting Danger choice."
    assert game.scene.acting is None
    with pytest.raises(ValueError, match="not fighting each other"):
        game.clash()
    game.set_hostile(True)
    assert game.clash().startswith("Dangers clash: rolled 3. Threshold 18, progress 8")


def test_undo_keeps_the_names_typed_since():
    game = heckboy_scene()
    game.commit_hits(5)
    game.rename_danger(0, "Bear")
    assert game.undo() == "Undid the last hits committed."
    assert (game.scene.progress, game.scene.dangers[0].name) == (0, "Bear")
    # A name typed after a removal stays on its own Danger when the removal is undone.
    game.remove_danger(0)
    game.rename_danger(0, "Jove")
    game.undo()
    assert [danger.name for danger in game.scene.dangers] == ["Bear", "Jove"]


def test_a_scene_saves_loads_and_recovers(tmp_path):
    game = heckboy_scene()
    game.rename_danger(0, "Bear")
    game.set_pc_count(3)
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
    assert "- Bear: Heavy Brute — threshold 6, 1 hit to pass" in loaded.history_text()
    assert loaded.history_text().count("Character:") == 0


def test_the_scenario_saves_loads_and_undoes_with_the_scene(tmp_path):
    game = heckboy_scene()
    assert game.add_scenario_danger("Colossus", DangerClass.TITAN, Difficulty.MEGA) == (
        "Added Colossus to the scenario."
    )
    game.add_scenario_danger("", DangerClass.BRUTE, Difficulty.HEAVY)
    game.type_into_scenario({(Slot.TEXT, "title"): "Night Ferry"})
    # Typed text is the GM's: undoing the Danger added before it keeps it.
    assert game.undo() == "Undid the last scenario Danger added."
    assert (game.scenario.title, len(game.scenario.dangers)) == ("Night Ferry", 1)
    assert game.change_scenario_danger(0, DangerClass.TITAN, Difficulty.BOSS) == (
        "Changed Colossus to Boss Titan."
    )

    game.name, game.path = "Friday", str(tmp_path / "gm.json")
    game.save()
    loaded = GmGame()
    loaded.load(*loaded.read_save(game.path))
    assert loaded.scenario == game.scenario
    assert "Scenario: Night Ferry — Colossus (Boss Titan)" in loaded.history_text()
    assert loaded.keep_scene(Genre.CORE) == (
        "Kit changed to Core WiD. Dropped Zeus. Dropped Colossus from the scenario."
    )


def test_a_scenario_danger_change_names_its_standing():
    game = GmGame()
    game.start_new(Genre.BALL_SEASON)
    game.add_scenario_danger("", DangerClass.BRUTE, Difficulty.HEAVY, Standing.ESTEEMED)
    assert (
        game.change_scenario_danger(0, DangerClass.BRUTE, Difficulty.HEAVY, Standing.SCANDALOUS)
        == "Changed Danger 1 to Heavy Brute, Scandalous."
    )


def scenario_game() -> GmGame:
    game = GmGame(rng=ScriptedRandom([4, 5, 2]))
    game.add_scenario_danger("The Lantern Man", DangerClass.BRUTE, Difficulty.HEAVY)
    game.add_scenario_danger("Moth Choir", DangerClass.SWARM, Difficulty.BOSS)
    return game


def test_a_scene_started_from_the_scenario_ends_once_overcome():
    game = scenario_game()
    assert game.start_scene(0) == "Scene started: The Lantern Man."
    with pytest.raises(ValueError, match="Overcome the scene"):
        game.end_scene()
    game.commit_hits(game.scene.threshold)
    game.type_scene_notes("Fled to the bus depot.")
    assert game.end_scene() == "Scene ended: The Lantern Man (Heavy Brute), progress 8 of 8."
    assert game.history[-1].notice.endswith("8 of 8.\nFled to the bus depot.")

    game.start_scene(1)
    assert (game.scene.progress, game.scene.notes, game.scene.scenario_danger_id) == (0, "", 1)


def test_the_next_scene_is_offered_the_next_scenario_danger():
    game = scenario_game()
    game.start_scene(1)
    # After the last Danger, the first again.
    assert game.next_scenario_index == 0
    game.lose_scene()
    game.start_scene(0)
    game.commit_hits(game.scene.threshold)
    game.end_scene()
    assert game.next_scenario_index == 1
    # A scene of the GM's own shows no scenario Danger's text.
    game.add_danger("Stray dog", DangerClass.BRUTE, Difficulty.PETTY)
    assert game.scene_from_scenario is None


def test_a_lost_scene_is_recorded_and_undone():
    game = scenario_game()
    game.start_scene(1)
    with pytest.raises(ValueError, match="End this scene first"):
        game.start_scene(0)
    game.type_scene_notes("Hums.")
    assert game.lose_scene().endswith("progress 0 of 12. They're dead. They're all dead!")
    assert game.undo() == "Undid the last lost scene."
    assert (game.scene.dangers[0].name, game.scene.notes) == ("Moth Choir", "Hums.")


def test_rolling_on_the_scenario_logs_its_entry():
    game = scenario_game()
    game.type_into_scenario(
        {("waypoints", 3): "The old bus depot", (Slot.INCITEMENT, 2): "A new Danger arrives"}
    )
    assert game.roll_on(ScenarioList.WAYPOINTS) == "Waypoints (4): The old bus depot."
    assert game.roll_on(Slot.INCITEMENT) == "Incitement (5): A new Danger arrives."
    assert game.roll_on(ScenarioList.NPCS) == "NPCs (2): nothing is written there."


def test_an_older_gm_save_upgrades_and_a_newer_one_is_refused():
    game = heckboy_scene()
    data = json.loads(game.saved_session("Friday").model_dump_json())
    # A 0.5.0 file (version 1): no ids, and the heavy difficulty called competent.
    for danger in data["scene"]["dangers"]:
        del danger["id"]
    del data["scene"]["next_id"]
    data["scene"]["dangers"][0]["difficulty"] = "competent"
    assert game.parse_save(json.dumps({**data, "version": 1})).scene == game.scene
    newer = GmSave.model_fields["version"].default + 1
    with pytest.raises(ValueError, match="saved by a newer wid"):
        game.parse_save(json.dumps({**data, "version": newer}))


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
