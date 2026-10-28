import pytest
from helpers import ScriptedRandom

from wid.game import Game
from wid.gm import GmGame
from wid.profiles import Genre
from wid.rolls import BonusKind, PowerMode
from wid.sessions import CharacterDetails


def started(genre=Genre.CORE, faces=(4,) * 40):
    game = Game(rng=ScriptedRandom(faces))
    if genre != Genre.CORE:
        game.change_kit(genre)
    game.start_game((1, 2, 3))
    return game


def test_a_roll_is_logged_and_clears_the_one_test_options():
    game = started(Genre.HECKBOY)
    game.assisted = True
    game.power = PowerMode.RELIABLE
    game.fear_level = 1
    assert game.roll("Ferocity") == ""
    request = game.session.current_result.request
    assert (request.attribute, request.assisted, request.power) == ("Ferocity", True, "reliable")
    assert str(game.history[-1]).startswith("Roll: heckboy, Ferocity rank 2")
    assert (game.assisted, game.power, game.fear_level) == (False, PowerMode.NONE, 1)


def test_bonuses_are_offered_once_named_and_logged_without_a_cost():
    game = started()
    game.session.set_bonus_name(BonusKind.APPROPRIATE_ITEM, "Sword")
    assert not game.bonus_available(BonusKind.APPROPRIATE_ITEM)
    game.roll()
    assert game.bonus_available(BonusKind.APPROPRIATE_ITEM)
    game.apply_bonus(BonusKind.APPROPRIATE_ITEM, 1)
    assert not game.bonus_available(BonusKind.APPROPRIATE_ITEM)
    assert "Appropriate Item Sword: +1 to die 2" in str(game.history[-1])


def test_undo_takes_back_the_last_changes_in_turn():
    game = started()
    game.rename("bonus", BonusKind.APPROPRIATE_ITEM, "Sword")
    game.assisted = True
    game.roll()
    rolled = game.session.current_result
    game.apply_bonus(BonusKind.APPROPRIATE_ITEM, 0)
    game.take_strain()
    game.rename("bonus", BonusKind.EXPERTISE, "Lockpicking")
    game.rename("strain", 0, "Broken arm")
    game.assisted = True
    assert game.undo() == "Undid the last strain change."
    assert not any(game.session.strain.boxes)
    assert (game.session.bonuses.expertise, game.session.strain.names[0]) == (
        "Lockpicking",
        "Broken arm",
    )
    assert game.assisted
    game.undo()
    assert game.session.current_result == rolled
    assert str(game.history[-1]).startswith("Undid the last bonus:")
    assert game.undo() == "Undid the last roll."
    assert (game.session.current_result, game.assisted) == (None, True)
    assert str(game.history[-1]) == "Undid the last roll."
    with pytest.raises(ValueError, match="nothing to undo"):
        game.undo()


def test_strain_and_standing_changes_are_logged():
    game = started(Genre.BALL_SEASON)
    game.take_strain()
    assert str(game.history[-1]) == "Took 1 strain: 1 strain, 0 wounds."
    game.set_standing(4)
    assert str(game.history[-1]) == "Standing moved to Scandalous (dot 5)."
    assert game.set_standing(4) == ""


def test_new_character_keeps_history_and_file_but_a_new_kit_starts_over():
    game = started()
    game.notes = "Keep the map"
    game.path = "game.json"
    game.character = CharacterDetails(name="Ada")
    game.roll()
    assert game.has_unsaved_state()
    assert game.new_character() == "New character started."
    assert game.session.attributes is None
    assert (game.notes, game.path, game.character.name) == ("Keep the map", "game.json", "")
    assert len(game.history) == 2
    assert game.change_kit(Genre.OLDHEART) == "New Oldheart game started."
    assert (game.history, game.notes, game.path) == ([], "", "")
    assert not game.has_unsaved_state()
    # A typed session name would be lost too.
    game.name = "Friday"
    assert game.has_unsaved_state()


def test_save_asks_before_replacing_and_load_restores_the_game(tmp_path):
    game = started(Genre.OLDHEART)
    game.roll("Depravity")
    game.fear_level = 2
    game.reroll_selection = (1,)
    game.path = str(tmp_path / "game.json")
    with pytest.raises(ValueError, match="Name the session before saving."):
        game.save()
    game.name = "Friday"
    assert game.save() == f"Saved Friday to {game.path}."
    assert not game.has_unsaved_state()
    with pytest.raises(FileExistsError) as error:
        game.save()
    assert error.value.filename == game.path
    game.save(overwrite=True)

    loaded = Game()
    saved, path = loaded.read_save(game.path)
    assert loaded.load(saved, path) == f"Loaded Friday from {game.path}."
    assert loaded.session.model_dump() == game.session.model_dump()
    assert (loaded.fear_level, loaded.reroll_selection) == (2, (1,))
    assert loaded.history == game.history
    assert not loaded.has_unsaved_state()
    loaded.roll()
    assert loaded.has_unsaved_state()
    with pytest.raises(ValueError, match="Could not load session"):
        loaded.read_save(str(tmp_path / "missing.json"))
    assert Game().open_file(game.path) == f"Loaded Friday from {game.path}."
    gm_path = tmp_path / "gm.json"
    GmGame().saved_session("GM").save(gm_path)
    with pytest.raises(ValueError, match="start wid with --gm"):
        Game().read_save(str(gm_path))
    with pytest.raises(ValueError, match="start wid without --gm"):
        GmGame().read_save(game.path)
    assert Game().open_file(str(tmp_path / "missing.json")).startswith("Could not load session")
    loaded.name, loaded.path = "Friday", str(tmp_path)
    with pytest.raises(ValueError, match="That path is a folder; add a file name."):
        loaded.save()
    loaded.path = str(tmp_path / "nope" / "game.json")
    with pytest.raises(ValueError) as error:
        loaded.save()
    assert str(error.value) == f"Could not save session: No such file or directory: {loaded.path}"


def test_unsaved_changes_are_kept_for_recovery_until_saved(tmp_path):
    recovery = tmp_path / "recovery.json"
    game = Game(rng=ScriptedRandom([4] * 8), recovery_path=recovery)
    game.start_game((1, 2, 3))
    game.roll()
    game.path = str(tmp_path / "game.json")
    assert game.keep_recovery() == ""
    assert recovery.is_file()

    restored = Game(recovery_path=recovery)
    assert restored.recovery_available()
    restored.restore_recovery()
    assert restored.session.model_dump() == game.session.model_dump()
    assert (restored.history, restored.name, restored.path) == (game.history, "", game.path)
    assert restored.has_unsaved_state()

    game.name = "Friday"
    game.save()
    game.keep_recovery()
    assert not recovery.exists()


def test_export_writes_markdown_beside_the_session_file(tmp_path):
    game = started()
    game.roll()
    game.path = str(tmp_path / "campaign.json")
    target = game.default_export_path()
    assert target == str(tmp_path / "campaign.md")
    assert game.export_history(target) == f"Exported 1 history entries to {target}."
    with pytest.raises(FileExistsError):
        game.export_history(target)
