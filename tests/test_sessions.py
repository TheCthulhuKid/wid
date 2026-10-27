import json
from random import Random

import pytest

from wid.profiles import Genre
from wid.rolls import RollRequest
from wid.sessions import SavedSession


@pytest.mark.parametrize("genre", list(Genre))
def test_every_kit_saves_loads_and_keeps_playing(tmp_path, genre, saved_session_factory):
    original = saved_session_factory(genre)
    path = tmp_path / "campaign.json"
    original.save(path)
    restored = SavedSession.load(path)
    assert restored.model_dump() == original.model_dump()
    restored.session.roll(restored.draft, rng=Random(3))


def test_save_before_the_first_roll(tmp_path, session_factory):
    draft = RollRequest(attribute="Composure", attribute_rank=2)
    saved = SavedSession(name="Ready to play", session=session_factory(), draft=draft)
    path = tmp_path / "unrolled.json"
    saved.save(path)
    assert SavedSession.load(path).session.current_result is None


def test_saving_never_overwrites_by_accident(tmp_path, saved_session_factory):
    saved = saved_session_factory()
    path = tmp_path / "session.json"
    saved.save(path)
    renamed = saved.model_copy(update={"name": "New name"})
    with pytest.raises(FileExistsError):
        renamed.save(path)
    renamed.save(path, overwrite=True)
    assert SavedSession.load(path).name == "New name"


def test_invalid_or_corrupt_files_are_rejected(tmp_path, saved_session_factory):
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        SavedSession.load(path)
    data = saved_session_factory().model_dump(mode="json")
    data["draft"]["attribute_rank"] = 3
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="assigned attribute rank"):
        SavedSession.load(path)
    data["version"] = 2
    with pytest.raises(ValueError, match="saved by a newer wid"):
        SavedSession.model_validate(data)
    data["version"] = [1]
    with pytest.raises(ValueError, match="unknown save format version"):
        SavedSession.model_validate(data)


def test_notes_are_saved_and_older_saves_load_without_them(tmp_path, saved_session_factory):
    data = saved_session_factory().model_dump(mode="json")
    data["notes"] = "Character: Ada 🎲"
    path = tmp_path / "notes.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert SavedSession.load(path).notes == "Character: Ada 🎲"
    data.pop("notes")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert SavedSession.load(path).notes == ""


def test_tech_needs_one_slot_per_muscle_rank(saved_session_factory):
    data = saved_session_factory(Genre.SECOND_CONTACT).model_dump()
    data["session"]["tech"]["pieces"] = data["session"]["tech"]["pieces"][:2]
    with pytest.raises(ValueError, match="one slot per Muscle rank"):
        SavedSession.model_validate(data)
