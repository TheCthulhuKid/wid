import json
from random import Random

import pytest
from helpers import read_saved

from wid.profiles import Genre
from wid.rolls import RollRequest
from wid.sessions import SavedSession, parse_save


@pytest.mark.parametrize("genre", list(Genre))
def test_every_kit_saves_loads_and_keeps_playing(tmp_path, genre, saved_session_factory):
    original = saved_session_factory(genre)
    path = tmp_path / "campaign.json"
    original.save(path)
    restored = read_saved(path)
    assert restored.model_dump() == original.model_dump()
    restored.session.roll(restored.draft, rng=Random(3))


def test_save_before_the_first_roll(tmp_path, session_factory):
    draft = RollRequest(attribute="Composure", attribute_rank=2)
    saved = SavedSession(name="Ready to play", session=session_factory(), draft=draft)
    path = tmp_path / "unrolled.json"
    saved.save(path)
    assert read_saved(path).session.current_result is None


def test_invalid_or_corrupt_files_are_rejected(tmp_path, saved_session_factory):
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_saved(path)
    data = saved_session_factory().model_dump(mode="json")
    data["version"] = 3
    with pytest.raises(ValueError, match="saved by a newer wid"):
        SavedSession.model_validate(data)
    with pytest.raises(ValueError, match="unknown save kind"):
        parse_save('{"kind": "referee"}', "player")


def test_an_older_save_loads_without_notes(tmp_path, saved_session_factory):
    data = saved_session_factory().model_dump(mode="json")
    path = tmp_path / "notes.json"
    data.pop("notes")
    data["version"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    older = read_saved(path)
    assert (older.notes, older.version) == ("", 2)
