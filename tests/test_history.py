from random import Random

import pytest
from pydantic import ValidationError

from wid.history import HistoryEntry
from wid.profiles import Genre
from wid.sessions import SavedSession


def test_notice_renders_as_its_text():
    assert str(HistoryEntry(notice="Switched kit")) == "Switched kit"


def test_entry_needs_exactly_one_kind(saved_session_factory):
    result = saved_session_factory().session.current_result

    with pytest.raises(ValidationError):
        HistoryEntry()
    with pytest.raises(ValidationError):
        HistoryEntry(notice="x", action="Roll", result=result)


def test_result_entry_needs_an_action(saved_session_factory):
    result = saved_session_factory().session.current_result

    with pytest.raises(ValidationError, match="needs an action"):
        HistoryEntry(result=result)


def test_result_entry_renders_snapshot_totals(saved_session_factory):
    session = saved_session_factory(Genre.HECKBOY).session
    entry = HistoryEntry(
        action="Roll", result=session.current_result, total_strain=session.total_strain
    )

    text = str(entry)

    assert text.startswith("Roll: heckboy, Aberrance rank 1;")
    assert "Strain +1 (session 1)" in text
    assert "Corruption" not in text
    assert "Tech remaining" not in text


def test_uncharged_entry_reports_no_cost(saved_session_factory):
    session = saved_session_factory(Genre.HECKBOY).session
    entry = HistoryEntry(
        action="Item", result=session.current_result, charged=False, total_strain=1
    )

    assert "Strain +0 (session 1)" in str(entry)


def test_structured_history_round_trips(tmp_path, saved_session_factory):
    saved = saved_session_factory(Genre.OLDHEART)
    result = saved.session.current_result
    entry = HistoryEntry(action="Roll", result=result, total_corruption=1, expertise_name="Fencing")
    saved = saved.model_copy(update={"history": (*saved.history, entry)})
    path = tmp_path / "game.json"

    saved.save(path)
    loaded = SavedSession.load(path)

    assert loaded.history == saved.history
    assert [str(item) for item in loaded.history] == [str(item) for item in saved.history]
    assert "Corruption +" in str(loaded.history[-1])
    assert result.dice == loaded.history[-1].result.dice


def test_rendering_after_reroll_uses_rolled_dice(saved_session_factory):
    saved = saved_session_factory(Genre.OLDHEART)
    before = HistoryEntry(action="Roll", result=saved.session.current_result)
    saved.session.reroll({1}, rng=Random(9))

    after = HistoryEntry(action="Reroll", result=saved.session.current_result)

    assert str(before) != str(after)
