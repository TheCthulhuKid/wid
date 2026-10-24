import json
from pathlib import Path
from random import Random

import pytest
from helpers import posix_only

from wid.profiles import PROFILES, Genre
from wid.rolls import RollRequest
from wid.sessions import SavedSession


@pytest.mark.parametrize("genre", list(Genre))
def test_round_trip_and_continued_play(tmp_path, genre, saved_session_factory):
    original = saved_session_factory(genre)
    path = tmp_path / "campaign.json"
    original.save(path)
    restored = SavedSession.load(path)
    assert restored.model_dump() == original.model_dump()
    assert restored.draft.fear_level == 2
    if genre == Genre.OLDHEART:
        restored.session.reroll({0}, rng=Random(3))
        assert restored.session.total_corruption == 2
        assert restored.session.current_result.totals().expertise_hits == 1
    else:
        restored.session.roll(restored.draft, rng=Random(3))
    assert original.session.model_dump() == SavedSession.load(path).session.model_dump()


def test_explicit_overwrite_and_failed_save_preserve_existing_file(
    tmp_path, monkeypatch, saved_session_factory
):
    original = saved_session_factory()
    path = tmp_path / "campaign.json"
    original.save(path)
    before = path.read_bytes()
    renamed = original.model_copy(update={"name": "Renamed"})
    with pytest.raises(FileExistsError):
        renamed.save(path)
    assert path.read_bytes() == before

    def fail_replace(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("wid.storage.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        renamed.save(path, overwrite=True)
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["campaign.json"]


def test_overwrite_and_missing_parent(tmp_path, saved_session_factory):
    saved = saved_session_factory()
    path = tmp_path / "session.json"
    saved.save(path)
    renamed = saved.model_copy(update={"name": "New name"})
    renamed.save(path, overwrite=True)
    assert SavedSession.load(path).name == "New name"
    with pytest.raises(OSError):
        saved.save(tmp_path / "missing" / "session.json")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(version=2),
        lambda data: data.update(name="   "),
        lambda data: data.update(reroll_indices=[0]),
        lambda data: data["draft"].update(fear_level=4),
        lambda data: data["draft"].update(attribute="unknown"),
        lambda data: data["draft"].update(attribute_rank=3),
        lambda data: data["session"].update(profile_id="oldheart"),
        lambda data: data["session"].update(total_corruption=1),
        lambda data: data["session"].update(attributes=None),
        lambda data: data["session"]["current_result"]["dice"][0].update(raw=9),
        lambda data: data["session"]["current_result"]["request"].update(attribute_rank=3),
        lambda data: data.update(item_target=2),
        lambda data: data.update(item_target=-1),
        lambda data: data.update(item_target=True),
        lambda data: data.update(item_target="0"),
        lambda data: data["session"].update(bonuses={"appropriate_item": 42}),
    ],
)
def test_invalid_snapshots_are_rejected(tmp_path, mutate, saved_session_factory):
    data = saved_session_factory().model_dump(mode="json")
    mutate(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        SavedSession.load(path)


@pytest.mark.parametrize("content", ["not json", "{}", "[]", '{"version": 999}'])
def test_corrupt_files_are_rejected(tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        SavedSession.load(path)


@posix_only
def test_unknown_home_directory_is_a_validation_error(saved_session_factory):
    path = Path("~wid_missing_user_8a5e/session.json")
    with pytest.raises(ValueError, match="home directory"):
        saved_session_factory().save(path)
    with pytest.raises(ValueError, match="home directory"):
        SavedSession.load(path)


@pytest.mark.parametrize("genre", list(Genre))
def test_save_before_first_roll(tmp_path, genre, session_factory):
    session = session_factory(genre, ranks=(3, 1, 2))
    draft = RollRequest(
        profile_id=genre,
        attribute=PROFILES[genre].attributes[2],
        attribute_rank=2,
        fear_level=3,
        assisted=True,
    )
    saved = SavedSession(name="Ready to play", session=session, draft=draft)
    path = tmp_path / "unrolled.json"
    saved.save(path)

    restored = SavedSession.load(path)
    assert restored.model_dump() == saved.model_dump()
    assert restored.session.current_result is None
    assert restored.history == ()
    result = restored.session.roll(restored.draft, rng=Random(5))
    assert len(result.dice) == 2
    assert result.request.attribute_rank == 2
    assert restored.session.total_strain == restored.session.total_corruption == 0
    assert restored.session.tech is None


@pytest.mark.parametrize("name", ["", " \t\n", "a" * 101])
def test_invalid_name_cannot_overwrite_file(tmp_path, saved_session_factory, name):
    saved = saved_session_factory()
    path = tmp_path / "session.json"
    saved.save(path)
    before = path.read_bytes()
    invalid = saved.model_copy(update={"name": name})

    with pytest.raises(ValueError):
        invalid.save(path, overwrite=True)

    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("name", ["x", "x" * 100, "  A dangerous evening 🎲  "])
def test_valid_name_boundaries_and_trimming(saved_session_factory, name):
    data = saved_session_factory().model_dump()
    data["name"] = name
    assert SavedSession.model_validate(data).name == name.strip()


def test_relative_path_round_trip(tmp_path, monkeypatch, saved_session_factory):
    monkeypatch.chdir(tmp_path)
    saved = saved_session_factory()
    saved.save(Path("campaign.json"))

    assert (tmp_path / "campaign.json").is_file()
    assert SavedSession.load(Path("campaign.json")).model_dump() == saved.model_dump()


@pytest.mark.parametrize("notes", ["", "  Character: Ada 🎲\n\n[b]Keep this literal[/b]\n  "])
def test_notes_round_trip_preserves_text(tmp_path, saved_session_factory, notes):
    data = saved_session_factory().model_dump()
    data["notes"] = notes
    saved = SavedSession.model_validate(data)
    path = tmp_path / "notes.json"
    saved.save(path)

    assert SavedSession.load(path).notes == notes


def test_older_save_without_notes_loads_empty(tmp_path, saved_session_factory):
    data = saved_session_factory().model_dump(mode="json")
    data.pop("notes")
    path = tmp_path / "older.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert SavedSession.load(path).notes == ""


@pytest.mark.parametrize("notes", [None, 42, ["a note"], {"text": "a note"}])
def test_invalid_notes_are_rejected(saved_session_factory, notes):
    data = saved_session_factory().model_dump()
    data["notes"] = notes
    with pytest.raises(ValueError):
        SavedSession.model_validate(data)


@pytest.mark.parametrize("genre", list(Genre))
def test_session_factory_returns_independent_games(session_factory, genre):
    first = session_factory(genre)
    second = session_factory(genre)
    request = RollRequest(profile_id=genre, attribute=PROFILES[genre].attributes[0])
    first.roll(request, rng=Random(1))

    assert second.current_result is None
    assert second.total_strain == second.total_corruption == 0
    assert second.tech is None
