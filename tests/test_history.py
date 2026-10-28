import pytest
from helpers import ScriptedRandom
from pydantic import ValidationError

from wid.history import ROLL_ACTION, HistoryEntry, history_statistics
from wid.profiles import Genre
from wid.rolls import RollRequest, RollSession


def test_an_entry_is_either_a_notice_or_an_action_with_its_result(saved_session_factory):
    result = saved_session_factory().session.current_result

    with pytest.raises(ValidationError, match="either a notice or a result"):
        HistoryEntry(notice="x", result=result)
    with pytest.raises(ValidationError, match="cannot set"):
        HistoryEntry(notice="Switched kit", total_strain=1)
    with pytest.raises(ValidationError, match="needs an action"):
        HistoryEntry(result=result)


def test_entries_render_their_notice_or_their_result_with_snapshot_totals(saved_session_factory):
    assert str(HistoryEntry(notice="Switched kit")) == "Switched kit"
    session = saved_session_factory(Genre.HECKBOY).session
    entry = HistoryEntry(
        action="Roll", result=session.current_result, total_strain=session.total_strain
    )

    text = str(entry)

    assert text.startswith("Roll: heckboy, Aberrance rank 1;")
    assert "Strain +1 (session 1)" in text
    assert "Corruption" not in text
    assert "Tech remaining" not in text
    uncharged = entry.model_copy(update={"action": "Item", "charged": False})
    assert "Strain +0 (session 1)" in str(uncharged)


def test_statistics_count_each_new_test_once():
    session = RollSession(profile_id=Genre.CORE)
    session.configure_attributes((1, 2, 3))
    first = session.roll(RollRequest(), rng=ScriptedRandom([6, 5, 3, 1]))
    second = session.roll(RollRequest(assisted=True), rng=ScriptedRandom([4, 4, 2, 1, 6]))
    history = [
        HistoryEntry(action=ROLL_ACTION, result=first),
        HistoryEntry(action="Reroll dice 1", result=first),
        HistoryEntry(action="Appropriate Item Sword: +1 to die 1", result=first, charged=False),
        HistoryEntry(notice="Took 1 strain: 1 strain, 0 wounds."),
        HistoryEntry(action=ROLL_ACTION, result=second),
    ]

    assert history_statistics(history) == (
        "2 tests, 9 dice as first rolled: 5 hits, 2 misses, 2 fumbles. Pools: 4d6 ×1, 5d6 ×1."
    )
    assert history_statistics(history[3:4]) == ""
