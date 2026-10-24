from random import Random

import pytest

from wid.profiles import PROFILES, Genre
from wid.rolls import PowerMode, RollRequest, RollSession
from wid.sessions import SavedSession


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
            tech_target=0 if genre == Genre.SECOND_CONTACT else None,
            item_allocations=() if genre == Genre.SECOND_CONTACT else (0, 0),
        )
        if genre == Genre.SECOND_CONTACT:
            session.initialize_tech()
        session.roll(request, rng=Random(1))
        if genre == Genre.OLDHEART:
            session.reroll({0}, rng=Random(2))
        return SavedSession(
            name="Friday's danger 🎲",
            session=session,
            draft=request,
            history=("First roll", "Second action"),
            reroll_indices=(0,) if genre == Genre.OLDHEART else (),
        )

    return create
