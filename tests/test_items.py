from random import Random

import pytest
from pydantic import ValidationError

from wid.profiles import PROFILES, Genre
from wid.rolls import (
    BonusKind,
    NamedBonuses,
    Outcome,
    PowerMode,
    RollRequest,
    RollSession,
)

ITEM_KINDS = (BonusKind.APPROPRIATE_ITEM, BonusKind.INAPPROPRIATE_ITEM)


def roll_test(session, **options):
    return session.roll(
        RollRequest(
            profile_id=session.profile_id,
            attribute=PROFILES[session.profile_id].attributes[0],
            **options,
        ),
        rng=Random(42),
    )


@pytest.mark.parametrize("genre", list(Genre))
def test_items_and_expertise_for_every_kit(session_factory, genre):
    session = session_factory(genre)
    for kind in BonusKind:
        session.set_bonus_name(kind, f"Named {kind.value}")
    initial = roll_test(session)
    initial_data = initial.model_dump()
    for index, kind in enumerate(ITEM_KINDS):
        previous = session.current_result
        result = session.apply_item(kind, index)
        assert result is session.current_result
        assert result.dice[index].bonus == previous.dice[index].bonus + 1
        assert result.dice[index].raw == previous.dice[index].raw
        assert result.request is previous.request
    before_expertise = session.current_result
    result = session.apply_expertise()
    assert result.request.expertise
    assert result.totals().hits == before_expertise.totals().hits + 1
    assert result.dice == before_expertise.dice
    assert initial.model_dump() == initial_data
    assert session.total_strain == session.total_corruption == 0
    with pytest.raises(ValidationError):
        result.dice[0].bonus = 99


@pytest.mark.parametrize("kind", ITEM_KINDS)
def test_an_item_works_once_per_test_and_again_after_a_new_roll(session_factory, kind):
    session = session_factory()
    session.set_bonus_name(kind, "Tool")
    roll_test(session)
    session.apply_item(kind, 0)
    before = session.model_dump()
    with pytest.raises(ValueError, match="already used"):
        session.apply_item(kind, 1)
    assert session.model_dump() == before
    roll_test(session)
    assert session.apply_item(kind, 1).dice[1].bonus == 1


@pytest.mark.parametrize("assisted", [False, True])
@pytest.mark.parametrize("kind", ITEM_KINDS)
def test_items_reclassify_fumbles_misses_and_hits(session_factory, kind, assisted):
    session = session_factory()
    session.set_bonus_name(kind, "Useful object")
    initial = roll_test(session, fear_level=2, assisted=assisted)
    assert initial.dice[1].raw == 1
    assert initial.dice[1].classify(initial.request) == Outcome.FUMBLE
    result = session.apply_item(kind, 1)
    assert result.dice[1].classify(result.request) == Outcome.MISS
    assert initial.dice[1].bonus == 0


@pytest.mark.parametrize("genre", [Genre.HECKBOY, Genre.SECOND_CONTACT, Genre.OLDHEART])
def test_modifiers_preserve_resources_and_result_costs(session_factory, genre):
    session = session_factory(genre)
    for kind in BonusKind:
        session.set_bonus_name(kind, kind.value)
    options = {}
    if genre == Genre.HECKBOY:
        options["power"] = PowerMode.ERRATIC
    if genre == Genre.SECOND_CONTACT:
        session.initialize_tech()
        options["tech_target"] = 0
    initial = roll_test(session, **options)
    if genre == Genre.OLDHEART:
        initial = session.reroll({0, 1}, rng=Random(1))
    before = session.model_dump(exclude={"current_result"})
    for kind in ITEM_KINDS:
        result = session.apply_item(kind, 0)
        assert result.strain_delta == initial.strain_delta
        assert result.corruption_delta == initial.corruption_delta
    result = session.apply_expertise()
    assert result.strain_delta == initial.strain_delta
    assert result.corruption_delta == initial.corruption_delta
    assert session.model_dump(exclude={"current_result"}) == before


def test_rerolls_preserve_modifiers_and_expertise_resets_only_for_new_test(
    session_factory,
):
    session = session_factory(Genre.OLDHEART)
    session.set_bonus_name("appropriate_item", "Sword")
    session.set_bonus_name("inappropriate_item", "Teacup")
    session.set_bonus_name("expertise", "Dueling")
    roll_test(session)
    session.apply_item("appropriate_item", 0)
    session.apply_item("inappropriate_item", 1)
    modified = session.apply_expertise()
    snapshot = modified.model_dump()
    for indices in ({0}, {0, 1}, {2, 3}):
        result = session.reroll(indices, rng=Random(2))
        assert [die.bonus for die in result.dice] == [1, 1, 0, 0]
        assert result.request.expertise
        assert result.totals().expertise_hits == 1
        before = session.model_dump()
        with pytest.raises(ValueError):
            session.apply_expertise()
        assert session.model_dump() == before
    assert modified.model_dump() == snapshot
    fresh = roll_test(session)
    assert not fresh.request.expertise
    assert all(die.bonus == 0 for die in fresh.dice)
    assert session.apply_expertise().totals().expertise_hits == 1


def test_expertise_cannot_be_applied_twice(session_factory):
    session = session_factory()
    initial = roll_test(session, expertise=True)
    session.set_bonus_name("expertise", "Training")
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.apply_expertise()
    assert session.model_dump() == before
    session.set_bonus_name("appropriate_item", "Tool")
    assert session.apply_item("appropriate_item", 0).dice[0].bonus == 1
    assert initial.dice[0].bonus == 0


def test_expertise_adds_a_hit_without_any_dice_hits(session_factory):
    session = session_factory()
    initial = session.roll(RollRequest(fear_level=3), rng=Random(1))
    assert initial.totals().hits == 0
    session.set_bonus_name("expertise", "Training")
    result = session.apply_expertise()
    assert result.totals().dice_hits == 0
    assert result.totals().hits == 1
    assert result.dice is initial.dice


@pytest.mark.parametrize("kind", list(BonusKind))
@pytest.mark.parametrize("name", ["", " \t\n"])
def test_relevant_name_required_before_action(session_factory, kind, name):
    session = session_factory()
    roll_test(session)
    for other in BonusKind:
        session.set_bonus_name(other, "Other named bonus")
    session.set_bonus_name(kind, name)
    before = session.model_dump()
    with pytest.raises(ValueError):
        if kind == BonusKind.EXPERTISE:
            session.apply_expertise()
        else:
            session.apply_item(kind, 0)
    assert session.model_dump() == before


@pytest.mark.parametrize("kind", ITEM_KINDS)
@pytest.mark.parametrize(
    "fear,index", [(0, i) for i in (True, False, -1, 4, 1000, 1.5, "0", None)] + [(3, 1)]
)
def test_invalid_item_indices_are_atomic(session_factory, kind, fear, index):
    session = session_factory()
    session.set_bonus_name(kind, "Tool")
    previous = roll_test(session, fear_level=fear)
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.apply_item(kind, index)
    assert session.model_dump() == before
    assert session.current_result is previous


@pytest.mark.parametrize("kind", ["expertise", "unknown", "", None, True, []])
def test_invalid_item_kinds_are_atomic(session_factory, kind):
    session = session_factory()
    session.set_bonus_name("expertise", "Training")
    roll_test(session)
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.apply_item(kind, 0)
    assert session.model_dump() == before


@pytest.mark.parametrize("wrong_profile", [False, True])
@pytest.mark.parametrize("kind", list(BonusKind))
def test_missing_or_wrong_profile_result_is_atomic(session_factory, wrong_profile, kind):
    session = session_factory()
    session.set_bonus_name(kind, "Named bonus")
    if wrong_profile:
        other = session_factory(Genre.OLDHEART)
        session.current_result = roll_test(other)
    before = session.model_dump()
    with pytest.raises(ValueError):
        if kind == BonusKind.EXPERTISE:
            session.apply_expertise()
        else:
            session.apply_item(kind, 0)
    assert session.model_dump() == before


@pytest.mark.parametrize(
    "kind,name",
    [
        ("unknown", "Name"),
        (None, "Name"),
        ([], "Name"),
        ("expertise", None),
        ("expertise", 1),
    ],
)
def test_invalid_name_updates_are_atomic(kind, name):
    session = RollSession()
    before = session.model_dump()
    with pytest.raises(ValueError):
        session.set_bonus_name(kind, name)
    assert session.model_dump() == before


def test_named_bonuses_defaults_immutable_updates_and_json_roundtrip(session_factory):
    assert NamedBonuses().model_dump() == {
        "expertise": "",
        "appropriate_item": "",
        "inappropriate_item": "",
    }
    session = session_factory()
    original = session.bonuses
    for kind, name in zip(BonusKind, ("Dueling 🎲", "Sword", "[b]Teacup[/b]"), strict=True):
        session.set_bonus_name(kind, name)
        assert getattr(session.bonuses, kind.value) == name
    assert original == NamedBonuses()
    with pytest.raises(ValidationError):
        session.bonuses.expertise = "Changed"
    roll_test(session)
    session.apply_item("appropriate_item", 0)
    session.apply_expertise()
    restored = RollSession.model_validate_json(session.model_dump_json())
    assert restored.model_dump() == session.model_dump()
    assert restored.apply_item("inappropriate_item", 0).dice[0].bonus == 2
    legacy = session.model_dump(exclude={"bonuses"})
    assert RollSession.model_validate(legacy).bonuses == NamedBonuses()


def test_undo_restores_the_roll_before_each_bonus_and_a_new_roll_clears_it(session_factory):
    session = session_factory(Genre.CORE)
    session.set_bonus_name(BonusKind.APPROPRIATE_ITEM, "Sword")
    session.set_bonus_name(BonusKind.INAPPROPRIATE_ITEM, "Teacup")
    original = roll_test(session)
    session.apply_item(BonusKind.APPROPRIATE_ITEM, 0)
    session.apply_item(BonusKind.INAPPROPRIATE_ITEM, 1)
    session.undo_bonus()
    assert session.undo_bonus() == original
    assert not session.can_undo_bonus
    assert session.apply_item(BonusKind.APPROPRIATE_ITEM, 0)
    roll_test(session)
    assert not session.can_undo_bonus
