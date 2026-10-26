from random import Random

import pytest

from wid.rolls import RollRequest, RollSession


def test_ranks_are_fixed_and_used_for_tests():
    session = RollSession()
    session.configure_attributes((2, 3, 1))
    result = session.roll(RollRequest(attribute="Composure", attribute_rank=3), rng=Random(1))
    assert result.request.attribute_rank == 3
    with pytest.raises(ValueError, match="fixed"):
        session.configure_attributes((1, 2, 3))
    with pytest.raises(ValueError, match="assigned"):
        session.roll(RollRequest(attribute="Composure", attribute_rank=1), rng=Random(1))


def test_ranks_must_be_unique_and_set_before_rolling():
    session = RollSession()
    with pytest.raises(ValueError, match="attributes"):
        session.roll(RollRequest(), rng=Random(1))
    with pytest.raises(ValueError, match="only once"):
        session.configure_attributes((1, 1, 3))
    assert session.attributes is None
