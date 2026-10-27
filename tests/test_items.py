from random import Random

import pytest

from wid.profiles import PROFILES, Genre
from wid.rolls import BonusKind, RollRequest


def roll_test(session, **options):
    return session.roll(
        RollRequest(
            profile_id=session.profile_id,
            attribute=PROFILES[session.profile_id].attributes[0],
            **options,
        ),
        rng=Random(42),
    )


def test_items_add_one_to_a_die_once_per_test(session_factory):
    session = session_factory()
    session.set_bonus_name(BonusKind.APPROPRIATE_ITEM, "Sword")
    initial = roll_test(session)
    result = session.apply_item(BonusKind.APPROPRIATE_ITEM, 1)
    assert result.dice[1].bonus == 1
    assert initial.dice[1].bonus == 0
    with pytest.raises(ValueError, match="already used"):
        session.apply_item(BonusKind.APPROPRIATE_ITEM, 0)
    roll_test(session)
    assert session.apply_item(BonusKind.APPROPRIATE_ITEM, 0).dice[0].bonus == 1


def test_a_bonus_needs_a_name_and_a_roll(session_factory):
    session = session_factory()
    with pytest.raises(ValueError, match="Roll a test"):
        session.apply_expertise()
    roll_test(session)
    with pytest.raises(ValueError, match="Name the appropriate item"):
        session.apply_item(BonusKind.APPROPRIATE_ITEM, 0)


def test_expertise_adds_one_hit_once(session_factory):
    session = session_factory()
    session.set_bonus_name(BonusKind.EXPERTISE, "Training")
    initial = roll_test(session)
    assert session.apply_expertise().totals().hits == initial.totals().hits + 1
    with pytest.raises(ValueError, match="already been applied"):
        session.apply_expertise()


def test_second_contact_has_no_items(session_factory):
    session = session_factory(Genre.SECOND_CONTACT)
    session.set_bonus_name(BonusKind.APPROPRIATE_ITEM, "Sword")
    roll_test(session)
    with pytest.raises(ValueError, match="Second Contact has no items"):
        session.apply_item(BonusKind.APPROPRIATE_ITEM, 0)
