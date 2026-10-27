import pytest
from pydantic import ValidationError

from wid.history import HistoryEntry
from wid.profiles import Genre


def test_notice_renders_as_its_text():
    assert str(HistoryEntry(notice="Switched kit")) == "Switched kit"


def test_an_entry_is_either_a_notice_or_an_action_with_its_result(saved_session_factory):
    result = saved_session_factory().session.current_result

    with pytest.raises(ValidationError, match="either a notice or a result"):
        HistoryEntry(notice="x", result=result)
    with pytest.raises(ValidationError, match="cannot set"):
        HistoryEntry(notice="Switched kit", total_strain=1)
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
