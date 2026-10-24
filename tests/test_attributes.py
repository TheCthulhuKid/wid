from itertools import permutations
from random import Random

import pytest

from wid.profiles import PROFILES, Genre
from wid.rolls import RollRequest, RollSession


@pytest.mark.parametrize("genre", list(Genre))
@pytest.mark.parametrize("ranks", list(permutations((1, 2, 3))))
def test_attribute_assignments_are_fixed_and_used_for_tests(genre, ranks):
    session = RollSession(profile_id=genre)
    session.configure_attributes(ranks)
    for attribute, rank in zip(PROFILES[genre].attributes, ranks, strict=True):
        result = session.roll(
            RollRequest(profile_id=genre, attribute=attribute, attribute_rank=rank), rng=Random(1)
        )
        assert result.request.attribute_rank == rank
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.configure_attributes((3, 2, 1))
    with pytest.raises(ValueError):
        session.roll(
            RollRequest(profile_id=genre, attribute=attribute, attribute_rank=rank % 3 + 1),
            rng=Random(1),
        )
    assert session.model_dump() == before


@pytest.mark.parametrize("genre", list(Genre))
@pytest.mark.parametrize(
    "ranks", [(1, 1, 3), (0, 2, 3), (1, 2, 4), (True, 2, 3), (), (1,), (1, 2), (1, 2, 3, 1)]
)
def test_invalid_setup_is_atomic(genre, ranks):
    session = RollSession(profile_id=genre)
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.configure_attributes(ranks)
    assert session.model_dump() == before


def test_setup_required_for_rolls_and_tech():
    session = RollSession(profile_id=Genre.SECOND_CONTACT)
    with pytest.raises(ValueError, match="attributes"):
        session.roll(RollRequest(profile_id=Genre.SECOND_CONTACT), rng=Random(1))
    with pytest.raises(ValueError, match="attributes"):
        session.initialize_tech()
    session.configure_attributes((3, 1, 2))
    assert session.initialize_tech().remaining_bonus == 4
    session.roll(
        RollRequest(profile_id=Genre.SECOND_CONTACT, attribute="Culture", tech_target=0),
        rng=Random(1),
    )
    assert session.tech.remaining_bonus == 3
    assert session.attribute_rank("Science") == 3
    assert session.tech.remaining_bonus == 3
    assert session.initialize_tech().remaining_bonus == 4


def test_unknown_attribute_and_cross_kit_setup_are_rejected():
    session = RollSession(profile_id=Genre.HECKBOY)
    setup = session.configure_attributes((1, 2, 3))
    before = session.model_dump()
    with pytest.raises(ValueError, match="belong"):
        session.roll(RollRequest(profile_id=Genre.HECKBOY, attribute="Science"), rng=Random(1))
    assert session.model_dump() == before
    with pytest.raises(ValueError, match="match"):
        RollSession(profile_id=Genre.OLDHEART, attributes=setup)
