from random import Random

import pytest
from pydantic import ValidationError

from wid.profiles import PROFILES, Genre
from wid.rolls import (
    DieResult,
    Outcome,
    PowerMode,
    RollRequest,
    RollResult,
    RollSession,
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


@pytest.mark.parametrize("assisted", [False, True])
@pytest.mark.parametrize("fear", range(4))
def test_pool(assisted, fear):
    request = RollRequest(assisted=assisted, fear_level=fear)
    result = configured_session().roll(request, rng=Random(42))
    assert len(result.dice) == 4 - fear + assisted
    assert request.hit_threshold == (4 if assisted else 5)
    totals = result.totals()
    assert totals.dice_hits + totals.misses + totals.fumbles == len(result.dice)


@pytest.mark.parametrize("rank", [1, 2, 3])
@pytest.mark.parametrize("assisted", [False, True])
@pytest.mark.parametrize("face", range(1, 7))
def test_every_face(rank, assisted, face):
    request = RollRequest(attribute_rank=rank, assisted=assisted)
    expected = (
        Outcome.HIT
        if face >= (4 if assisted else 5)
        else (Outcome.FUMBLE if face <= rank else Outcome.MISS)
    )
    assert DieResult(raw=face).classify(request) == expected


def test_expertise_and_fumbles_at_a_higher_rank():
    request = RollRequest(attribute_rank=2, expertise=True)
    result = configured_session(ranks=(2, 1, 3)).roll(request, rng=ScriptedRandom([6, 2, 1, 4]))
    assert [die.effective for die in result.dice] == [6, 2, 1, 4]
    assert result.totals().model_dump() == {
        "dice_hits": 1,
        "expertise_hits": 1,
        "misses": 1,
        "fumbles": 2,
    }
    zero_hits = configured_session().roll(RollRequest(expertise=True), rng=ScriptedRandom([1] * 4))
    assert zero_hits.totals().hits == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"attribute_rank": 0},
        {"attribute_rank": 4},
        {"fear_level": -1},
        {"fear_level": 4},
        {"fear_level": True},
        {"power": "reliable"},
        {"tech_target": 0},
    ],
)
def test_invalid_request(changes):
    with pytest.raises(ValidationError):
        RollRequest(**changes)


def test_failed_generation_and_invalid_request_are_atomic():
    session = configured_session()
    previous = session.roll(RollRequest(), rng=Random(1))
    before = session.model_dump()
    with pytest.raises(ValidationError):
        session.roll(RollRequest(), rng=ScriptedRandom([1, 7]))
    assert session.model_dump() == before
    with pytest.raises(ValueError):
        session.roll(RollRequest(profile_id=Genre.OLDHEART), rng=Random(1))
    assert session.current_result is previous
    with pytest.raises(ValidationError):
        RollResult(request=RollRequest(), dice=[])


def test_result_snapshot_is_immutable():
    request = RollRequest()
    with pytest.raises(ValidationError):
        request.fear_level = 3


@pytest.mark.parametrize(
    "power,cost", [(PowerMode.NONE, 0), (PowerMode.RELIABLE, 1), (PowerMode.ERRATIC, 2)]
)
@pytest.mark.parametrize("assisted", [False, True])
@pytest.mark.parametrize("fear", range(4))
def test_heckboy_pools_and_strain(power, cost, assisted, fear):
    session = configured_session(Genre.HECKBOY)
    request = RollRequest(
        profile_id=Genre.HECKBOY,
        attribute="Aberrance",
        power=power,
        assisted=assisted,
        fear_level=fear,
    )
    result = session.roll(request, rng=Random(3))
    assert len(result.dice) == 4 - fear + assisted + cost
    assert result.strain_delta == session.total_strain == cost
    result.totals()
    assert session.total_strain == cost
    before = session.model_dump()
    with pytest.raises(ValidationError):
        session.roll(request, rng=ScriptedRandom([9]))
    assert session.model_dump() == before
    session.roll(request, rng=Random(2))
    assert session.total_strain == 2 * cost


@pytest.mark.parametrize("genre", [g for g in Genre if g != Genre.HECKBOY])
def test_power_incompatible_kits(genre):
    with pytest.raises(ValidationError):
        RollRequest(profile_id=genre, power=PowerMode.ERRATIC)


def test_tech_consumption_and_depletion():
    session = configured_session(Genre.SECOND_CONTACT, (2, 3, 1))
    request = RollRequest(
        profile_id=Genre.SECOND_CONTACT,
        attribute="Science",
        attribute_rank=2,
        tech_target=1,
    )
    with pytest.raises(ValueError):
        session.roll(request, rng=Random(0))
    tech = session.initialize_tech()
    assert tech.remaining_bonus == 5
    for strength in range(5, 0, -1):
        result = session.roll(request, rng=ScriptedRandom([1, 2, 3, 4]))
        assert [die.bonus for die in result.dice] == [0, strength, 0, 0]
        assert result.dice[1].effective == 2 + strength
        assert session.tech.remaining_bonus == strength - 1
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.roll(request, rng=Random(0))
    assert session.model_dump() == before
    session.roll(
        RollRequest(profile_id=Genre.SECOND_CONTACT, attribute="Science", attribute_rank=2),
        rng=Random(0),
    )
    assert session.tech.remaining_bonus == 0
    session.initialize_tech()
    assert session.tech.remaining_bonus == 5


def test_invalid_tech_actions_are_atomic():
    session = configured_session(Genre.SECOND_CONTACT)
    session.initialize_tech()
    before = session.model_dump()
    request = RollRequest(profile_id=Genre.SECOND_CONTACT, attribute="Science", tech_target=0)
    with pytest.raises(ValidationError):
        session.roll(request, rng=ScriptedRandom([6, 6, 9]))
    assert session.model_dump() == before
    with pytest.raises(ValidationError):
        RollRequest(profile_id=Genre.SECOND_CONTACT, tech_target=4)
    with pytest.raises(ValidationError):
        RollRequest(profile_id=Genre.SECOND_CONTACT, fear_level=3, tech_target=1)
    for genre in Genre:
        if genre == Genre.SECOND_CONTACT:
            continue
        other = RollSession(profile_id=genre)
        with pytest.raises(ValueError):
            other.initialize_tech()
        assert other.tech is None
        with pytest.raises(ValidationError):
            RollRequest(profile_id=genre, tech_target=0)


def test_oldheart_subset_repeated_rerolls_and_immutable_snapshots():
    session = configured_session(Genre.OLDHEART, (2, 1, 3))
    request = RollRequest(
        profile_id=Genre.OLDHEART,
        attribute="Depravity",
        attribute_rank=2,
        expertise=True,
    )
    session.set_bonus_name("appropriate_item", "Sword")
    initial = session.roll(request, rng=ScriptedRandom([1, 2, 3, 4]))
    initial_snapshot = initial.model_dump()
    session.apply_item("appropriate_item", 0)
    first = session.reroll({0, 2}, rng=ScriptedRandom([6, 1]))
    assert [die.raw for die in first.dice] == [6, 2, 1, 4]
    assert [die.bonus for die in first.dice] == [1, 0, 0, 0]
    assert first.dice[1] is initial.dice[1]
    assert first.dice[3] is initial.dice[3]
    assert first.request == request
    assert first.corruption_delta == session.total_corruption == 2
    assert first.strain_delta == 0
    assert first.totals().hits == 2
    second = session.reroll({0}, rng=ScriptedRandom([1]))
    assert second.dice[0].effective == 2
    assert second.corruption_delta == 1
    assert session.total_corruption == 3
    assert second.totals().hits == 1
    assert second.totals().expertise_hits == 1
    assert initial.model_dump() == initial_snapshot
    assert first.dice[0].raw == 6
    third = session.reroll(set(range(4)), rng=ScriptedRandom([4] * 4))
    assert third.corruption_delta == 4
    assert session.total_corruption == 7
    totals = third.totals()
    assert totals.dice_hits + totals.misses + totals.fumbles == 4


def test_oldheart_invalid_actions_do_not_charge_or_change_results():
    session = configured_session(Genre.OLDHEART)
    with pytest.raises(ValueError):
        session.reroll({0}, rng=Random(0))
    request = RollRequest(profile_id=Genre.OLDHEART, attribute="Depravity")
    session.roll(request, rng=Random(0))
    before = session.model_dump()
    for indices in [set(), {-1}, {4}, {0, 4}, {True}, {1.5}]:
        with pytest.raises(ValueError):
            session.reroll(indices, rng=Random(0))
        assert session.model_dump() == before
    with pytest.raises(ValidationError):
        session.reroll({0, 2}, rng=ScriptedRandom([1, 9]))
    assert session.model_dump() == before
    for genre in Genre:
        if genre == Genre.OLDHEART:
            continue
        other = configured_session(genre)
        other.roll(
            RollRequest(profile_id=genre, attribute=PROFILES[genre].attributes[0]),
            rng=Random(0),
        )
        before = other.model_dump()
        with pytest.raises(ValueError):
            other.reroll({0}, rng=Random(0))
        assert other.model_dump() == before
