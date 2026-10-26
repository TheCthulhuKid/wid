from random import Random

import pytest

from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import PowerMode, RollRequest, RollSession
from wid.sessions import SavedSession


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path_factory, monkeypatch):
    """Keep tests from reading or writing the real user configuration."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))


@pytest.fixture
def session_factory():
    def create(genre=Genre.CORE, ranks=(1, 2, 3)):
        session = RollSession(profile_id=genre)
        session.configure_attributes(ranks)
        return session

    return create


@pytest.fixture
def saved_session_factory(session_factory):
    def create(genre=Genre.CORE):
        session = session_factory(genre)
        request = RollRequest(
            profile_id=genre,
            attribute=PROFILES[genre].attributes[0],
            fear_level=2,
            expertise=True,
            power=PowerMode.RELIABLE if genre == Genre.HECKBOY else PowerMode.NONE,
        )
        session.roll(request, rng=Random(1))
        if genre == Genre.SECOND_CONTACT:
            session.set_tech_name(0, "Translator")
            session.apply_tech(0, 0)
        if genre == Genre.OLDHEART:
            session.reroll({0}, rng=Random(2))
        return SavedSession(
            name="Friday's danger 🎲",
            session=session,
            draft=request,
            history=(HistoryEntry(notice="First roll"), HistoryEntry(notice="Second action")),
            reroll_indices=(0,) if genre == Genre.OLDHEART else (),
        )

    return create
