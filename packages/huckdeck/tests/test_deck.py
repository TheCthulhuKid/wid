from random import Random

import pytest
from pydantic import ValidationError

from huckdeck.deck import Card, Deck, Rank, Suit, SuitDescription


@pytest.fixture
def fresh_deck():
    return Deck()


def test_standard_deck_has_56_unique_cards_and_four_suited_jokers(fresh_deck):
    assert len(fresh_deck.cards) == 56
    assert len(set(fresh_deck.cards)) == 56
    assert {card.suit for card in fresh_deck.cards if card.rank == Rank.JOKER} == set(Suit)
    assert all(sum(card.suit == suit for card in fresh_deck.cards) == 14 for suit in Suit)
    assert fresh_deck.dealt == fresh_deck.aces == ()
    assert fresh_deck.current_card is None


def test_draw_tracks_aces_and_remaining_cards_without_duplicates(fresh_deck):
    original = fresh_deck.cards
    for index, expected in enumerate(original, 1):
        assert fresh_deck.draw() == expected
        assert fresh_deck.current_card == expected
        assert fresh_deck.cards == original[index:]
        assert fresh_deck.dealt == original[:index]
        assert fresh_deck.aces == tuple(card for card in original[:index] if card.rank == Rank.ACE)
    assert len(fresh_deck.aces) == 4
    before = fresh_deck.model_dump()
    with pytest.raises(ValueError, match="Not enough cards"):
        fresh_deck.draw()
    assert fresh_deck.model_dump() == before


@pytest.mark.parametrize("count", [0, -1, 57, True, False, 1.5, "1", None])
def test_invalid_deals_do_not_change_state(fresh_deck, count):
    before = fresh_deck.model_dump()
    with pytest.raises(ValueError):
        fresh_deck.deal(count)
    assert fresh_deck.model_dump() == before


def test_multi_card_deal_and_shuffle_restore_every_card(fresh_deck):
    fresh_deck.set_description(Suit.HEARTS, "Love and danger ♥")
    original = fresh_deck.cards
    assert fresh_deck.deal(17) == list(original[:17])
    expected = [*original[17:], *original[:17]]
    Random(22).shuffle(expected)
    fresh_deck.shuffle(rng=Random(22))
    assert fresh_deck.cards == tuple(expected)
    assert set(fresh_deck.cards) == set(original)
    assert fresh_deck.dealt == fresh_deck.aces == ()
    assert fresh_deck.current_card is None
    assert fresh_deck.description_for(Suit.HEARTS) == "Love and danger ♥"


@pytest.mark.parametrize("rank", [Rank.ACE, Rank.JOKER, Rank.KING])
def test_draw_chain_continues_after_aces_and_jokers(fresh_deck, rank):
    first = next(card for card in fresh_deck.cards if card.rank == rank)
    following = next(card for card in fresh_deck.cards if card.rank == Rank.TWO)
    rest = tuple(card for card in fresh_deck.cards if card not in (first, following))
    deck = Deck(cards=(first, following, *rest))
    expected = (first,) if rank == Rank.KING else (first, following)
    assert deck.draw_chain() == list(expected)
    assert deck.dealt == expected
    assert deck.current_card == expected[-1]
    assert len(deck.cards) + len(deck.dealt) == 56
    assert deck.aces == tuple(card for card in expected if card.rank == Rank.ACE)


@pytest.mark.parametrize("exhausted", [False, True])
def test_draw_chain_handles_consecutive_special_cards_and_exhaustion(fresh_deck, exhausted):
    special = tuple(card for card in fresh_deck.cards if card.rank in (Rank.ACE, Rank.JOKER))
    ordinary = tuple(card for card in fresh_deck.cards if card not in special)
    deck = Deck(
        cards=special if exhausted else (*special, *ordinary), dealt=ordinary if exhausted else ()
    )
    expected = special if exhausted else (*special, ordinary[0])
    assert deck.draw_chain() == list(expected)
    assert deck.current_card == expected[-1]
    assert len(deck.aces) == 4
    if exhausted:
        assert not deck.cards
        before = deck.model_dump()
        with pytest.raises(ValueError, match="Not enough cards"):
            deck.draw_chain()
        assert deck.model_dump() == before
    else:
        assert deck.cards == ordinary[1:]


def test_shuffle_exhausted_deck(fresh_deck):
    original = set(fresh_deck.cards)
    fresh_deck.deal(56)
    fresh_deck.shuffle(rng=Random(1))
    assert set(fresh_deck.cards) == original
    assert not fresh_deck.dealt


@pytest.mark.parametrize("suit", Suit)
def test_suit_descriptions_are_independent_and_can_be_cleared(fresh_deck, suit):
    fresh_deck.set_description(suit, "[bold]Literal description ♠")
    assert fresh_deck.description_for(suit) == "[bold]Literal description ♠"
    assert all(fresh_deck.description_for(other) == "" for other in Suit if other != suit)
    assert Deck().description_for(suit) == ""
    before = fresh_deck.model_dump()
    with pytest.raises(ValidationError):
        fresh_deck.set_description(suit, None)
    assert fresh_deck.model_dump() == before
    fresh_deck.set_description(suit, "")
    assert fresh_deck.description_for(suit) == ""


def test_incomplete_or_duplicate_cards_and_descriptions_are_rejected(fresh_deck):
    with pytest.raises(ValidationError, match="56 suited cards"):
        Deck(cards=fresh_deck.cards[:-1])
    with pytest.raises(ValidationError, match="56 suited cards"):
        Deck(cards=(*fresh_deck.cards[:-1], fresh_deck.cards[0]))
    with pytest.raises(ValidationError, match="56 suited cards"):
        Deck(dealt=(fresh_deck.cards[0],))
    with pytest.raises(ValidationError, match="one description"):
        Deck(descriptions=(SuitDescription(suit=Suit.HEARTS),) * 4)
    with pytest.raises(ValidationError):
        Card(suit=Suit.HEARTS, rank="15")


def test_failed_shuffle_is_atomic(fresh_deck):
    class BrokenRandom(Random):
        def shuffle(self, cards):
            cards.clear()
            raise RuntimeError("Failed shuffle")

    fresh_deck.draw()
    before = fresh_deck.model_dump()
    with pytest.raises(RuntimeError, match="Failed shuffle"):
        fresh_deck.shuffle(rng=BrokenRandom())
    assert fresh_deck.model_dump() == before


def test_deck_round_trip_and_compatibility_imports(fresh_deck):
    from deck import Card as CompatibilityCard
    from deck import Deck as CompatibilityDeck

    fresh_deck.deal(20)
    fresh_deck.set_description(Suit.SPADES, "Trouble")
    assert Deck.model_validate_json(fresh_deck.model_dump_json()) == fresh_deck
    assert CompatibilityDeck is Deck
    assert CompatibilityCard is Card
