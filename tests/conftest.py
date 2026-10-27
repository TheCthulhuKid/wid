from random import Random

import pytest

from wid.history import HistoryEntry
from wid.profiles import PROFILES, Genre
from wid.rolls import PowerMode, ResourceEffect, RollRequest, RollSession, StrainTracker
from wid.sessions import CharacterDetails, SavedSession


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


def wounded(session):
    session.strain = StrainTracker().take(4).set_name(0, "Broken arm")


def tech_used(session):
    session.set_tech_name(0, "Translator")
    session.apply_tech(0, 0)


def manifested(session):
    session.reroll({0}, rng=Random(2))
    session.set_manifestation_name(0, "Milky eye")


def resources_spent(session):
    session.adjust_resources(3)
    session.spend_resources(ResourceEffect.EXTRA_DIE, rng=Random(0))


# What each kit has of its own after its first roll, so one save and load covers all of it.
KIT_SETUP = {
    Genre.CORE: wounded,
    Genre.HECKBOY: lambda session: session.set_power_name(0, "Hellfire"),
    Genre.SECOND_CONTACT: tech_used,
    Genre.OLDHEART: manifested,
    Genre.BALL_SEASON: lambda session: session.set_standing(0),
    Genre.THIS_ISNT_HAPPENING: resources_spent,
}


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
        result = session.roll(request, rng=Random(1))
        KIT_SETUP[genre](session)
        return SavedSession(
            name="Friday's danger 🎲",
            session=session,
            # The reroll's manifestation check may have changed the pool for the next test.
            draft=request.model_copy(update={"manifestations": len(session.manifestations)}),
            notes="**Keep** the map.",
            character=CharacterDetails(name="Ada 🎲", looks="Red coat"),
            history=(
                HistoryEntry(action="Roll", result=result, total_strain=session.total_strain),
                HistoryEntry(notice="Second action"),
            ),
            reroll_indices=(0,) if genre == Genre.OLDHEART else (),
        )

    return create
