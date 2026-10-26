from random import Random

import pytest
from pydantic import ValidationError

from wid.profiles import PROFILES, Genre
from wid.rolls import (
    DieResult,
    Outcome,
    PowerMode,
    RollRequest,
    RollSession,
    TechPiece,
)


class ScriptedRandom(Random):
    def __init__(self, faces):
        self.faces = iter(faces)

    def randint(self, a, b):
        return next(self.faces)


def configured_session(genre=Genre.CORE, ranks=None):
    session = RollSession(profile_id=genre)
    session.configure_attributes(ranks or tuple(range(1, len(PROFILES[genre].attributes) + 1)))
    return session


def test_pool_size_and_hit_threshold():
    assert RollRequest().pool_size() == 4
    assisted = RollRequest(assisted=True, fear_level=2)
    assert assisted.pool_size() == 3
    assert assisted.hit_threshold == 4
    assert RollRequest().hit_threshold == 5


def test_dice_are_hits_misses_or_fumbles():
    request = RollRequest(attribute_rank=2)
    assert [DieResult(raw=face).classify(request) for face in (6, 3, 2)] == [
        Outcome.HIT,
        Outcome.MISS,
        Outcome.FUMBLE,
    ]


def test_roll_counts_dice_and_expertise():
    request = RollRequest(attribute_rank=2, expertise=True)
    result = configured_session(ranks=(2, 1, 3)).roll(request, rng=ScriptedRandom([6, 2, 1, 4]))
    assert result.totals().model_dump() == {
        "dice_hits": 1,
        "expertise_hits": 1,
        "misses": 1,
        "fumbles": 2,
    }


def test_invalid_roll_changes_nothing():
    session = configured_session()
    session.roll(RollRequest(), rng=Random(1))
    before = session.model_dump()
    with pytest.raises(ValidationError):
        session.roll(RollRequest(), rng=ScriptedRandom([1, 7]))
    assert session.model_dump() == before
    with pytest.raises(ValidationError):
        RollRequest(fear_level=4)


def test_heckboy_powers_add_dice_and_strain():
    session = configured_session(Genre.HECKBOY)
    request = RollRequest(profile_id=Genre.HECKBOY, attribute="Aberrance", power=PowerMode.ERRATIC)
    result = session.roll(request, rng=Random(3))
    assert len(result.dice) == 6
    assert result.strain_delta == session.total_strain == 2
    with pytest.raises(ValidationError, match="Only Heckboy"):
        RollRequest(power=PowerMode.RELIABLE)


def test_tech_slots_start_empty_and_a_new_scenario_empties_them():
    session = configured_session(Genre.SECOND_CONTACT, (2, 3, 1))
    assert session.tech.pieces == (TechPiece(strength=5),)
    session.set_tech_name(0, "Drone")
    assert session.start_scenario().pieces == (TechPiece(strength=5),)
    assert configured_session().tech is None


def test_tech_is_applied_after_the_roll_and_weakens_by_one():
    session = configured_session(Genre.SECOND_CONTACT, (1, 2, 3))
    request = RollRequest(profile_id=Genre.SECOND_CONTACT, attribute="Muscle", attribute_rank=3)
    session.roll(request, rng=ScriptedRandom([1, 2, 3, 4]))
    with pytest.raises(ValueError, match="Name Tech 2 before using it"):
        session.apply_tech(1, 0)
    session.set_tech_name(1, "Drone")
    assert [die.bonus for die in session.apply_tech(1, 1).dice] == [0, 3, 0, 0]
    assert session.tech.pieces[1].strength == 2
    with pytest.raises(ValueError, match="Drone was already used on this test"):
        session.apply_tech(1, 0)
    session.undo_bonus()
    assert session.tech.pieces[1].strength == 3


def test_sacrifice_zeroes_a_named_piece():
    session = configured_session(Genre.SECOND_CONTACT, (1, 2, 3))
    with pytest.raises(ValueError, match="Name Tech 2 before sacrificing it"):
        session.sacrifice_tech(1)
    session.set_tech_name(1, "Drone")
    assert session.sacrifice_tech(1) == TechPiece(name="Drone", strength=3)
    assert [piece.strength for piece in session.tech.pieces] == [3, 0, 3]
    with pytest.raises(ValueError, match="Drone is already at 0"):
        session.sacrifice_tech(1)


def test_oldheart_rerolls_keep_bonuses_and_add_corruption():
    session = configured_session(Genre.OLDHEART, (2, 1, 3))
    request = RollRequest(profile_id=Genre.OLDHEART, attribute="Depravity", attribute_rank=2)
    session.set_bonus_name("appropriate_item", "Sword")
    initial = session.roll(request, rng=ScriptedRandom([1, 2, 3, 4]))
    session.apply_item("appropriate_item", 0)
    result = session.reroll({0, 2}, rng=ScriptedRandom([6, 1]))
    assert [die.raw for die in result.dice] == [6, 2, 1, 4]
    assert [die.bonus for die in result.dice] == [1, 0, 0, 0]
    assert result.corruption_delta == session.total_corruption == 2
    assert initial.dice[0].raw == 1
    with pytest.raises(ValueError, match="Only Oldheart"):
        configured_session().reroll({0}, rng=Random(0))
