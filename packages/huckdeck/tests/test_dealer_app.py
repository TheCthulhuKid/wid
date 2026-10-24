import asyncio
import runpy
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path
from random import Random
from unittest.mock import patch

import pytest
from rich.console import Console
from textual.widgets import Button, Input, Static

from huckdeck.cli import main
from huckdeck.deck import Deck, Rank, Suit
from huckdeck.ui.app import HuckDeck, card_art


@pytest.fixture
def ordered_dealer():
    return HuckDeck(deck=Deck(), rng=Random(4))


def text(app, selector):
    return str(app.query_one(selector, Static).content)


def test_mouse_deal_updates_card_aces_counts_and_remaining(ordered_dealer):
    async def scenario():
        async with ordered_dealer.run_test(size=(100, 40)) as pilot:
            assert "56 left" in text(ordered_dealer, "#card-count")
            await pilot.click("#deal-card")
            assert ordered_dealer.deck.current_card.rank == Rank.TWO
            assert "54 left" in text(ordered_dealer, "#card-count")
            assert "1 / 4 aces dealt" in text(ordered_dealer, "#ace-tracker")
            assert "A♥ Hearts: dealt" in text(ordered_dealer, "#ace-tracker")
            hearts = text(ordered_dealer, "#remaining-cards").splitlines()[0]
            assert hearts == "♥ Hearts: 3 4 5 6 7 8 9 10 J Q K Joker"
            assert text(ordered_dealer, "#dealt-cards") == "A♥ · 2♥"
            assert text(ordered_dealer, "#dealer-status") == "Dealt A of Hearts → 2 of Hearts"
            await pilot.press("ctrl+d")
            assert ordered_dealer.deck.current_card.rank == Rank.THREE
            assert "53 left" in text(ordered_dealer, "#card-count")
            assert "1 / 4 aces dealt" in text(ordered_dealer, "#ace-tracker")

    asyncio.run(scenario())


@pytest.mark.parametrize("exhausted", [False, True])
def test_keyboard_deals_special_chain_and_shows_every_card(exhausted):
    source = Deck()
    special = tuple(card for card in source.cards if card.rank in (Rank.ACE, Rank.JOKER))
    ordinary = tuple(card for card in source.cards if card not in special)
    deck = Deck(
        cards=special if exhausted else (*special, *ordinary), dealt=ordinary if exhausted else ()
    )

    async def scenario():
        app = HuckDeck(deck=deck)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("ctrl+d")
            expected = special if exhausted else (*special, ordinary[0])
            assert app.deck.current_card == expected[-1]
            assert " → ".join(str(card) for card in expected) in text(app, "#dealer-status")
            assert "4 / 4 aces dealt" in text(app, "#ace-tracker")
            assert app.query_one("#deal-card", Button).disabled == exhausted
            if exhausted:
                assert "Deck exhausted" in text(app, "#dealer-status")
                assert "0 left" in text(app, "#card-count")
            else:
                assert app.deck.cards == ordinary[1:]
            assert len(app.deck.cards) + len(app.deck.dealt) == 56

    asyncio.run(scenario())


def test_suit_descriptions_update_current_card_and_survive_shuffle(ordered_dealer):
    async def scenario():
        async with ordered_dealer.run_test(size=(100, 40)) as pilot:
            await pilot.click("#deal-card")
            await pilot.click("#description-hearts")
            await pilot.press(*"Danger")
            assert ordered_dealer.deck.description_for(Suit.HEARTS) == "Danger"
            assert card_art(ordered_dealer.deck).subtitle.plain == "Danger"
            await pilot.click("#shuffle-deck")
            before = ordered_dealer.deck.model_dump()
            await pilot.press("ctrl+d", "ctrl+s")
            assert ordered_dealer.deck.model_dump() == before
            await pilot.click("#cancel-shuffle")
            assert ordered_dealer.deck.model_dump() == before
            await pilot.click("#shuffle-deck")
            await pilot.click("#confirm-shuffle")
            assert "56 left" in text(ordered_dealer, "#card-count")
            assert "0 / 4 aces dealt" in text(ordered_dealer, "#ace-tracker")
            assert ordered_dealer.deck.current_card is None
            assert ordered_dealer.query_one("#description-hearts", Input).value == "Danger"

    asyncio.run(scenario())


def test_exhaustion_and_keyboard_shuffle(ordered_dealer):
    async def scenario():
        async with ordered_dealer.run_test(size=(80, 24)) as pilot:
            for _ in range(56):
                ordered_dealer.action_deal()
            assert "0 left" in text(ordered_dealer, "#card-count")
            assert "4 / 4 aces dealt" in text(ordered_dealer, "#ace-tracker")
            assert ordered_dealer.query_one("#deal-card", Button).disabled
            before = ordered_dealer.deck.model_dump()
            await pilot.press("ctrl+d")
            assert ordered_dealer.deck.model_dump() == before
            assert "Not enough cards" in text(ordered_dealer, "#dealer-status")
            await pilot.press("ctrl+s")
            await pilot.click("#confirm-shuffle")
            assert len(ordered_dealer.deck.cards) == 56
            assert not ordered_dealer.query_one("#deal-card", Button).disabled

    asyncio.run(scenario())


@pytest.mark.parametrize("suit", Suit)
@pytest.mark.parametrize("rank", [Rank.ACE, Rank.TEN, Rank.JOKER])
def test_card_symbols_and_literal_descriptions(suit, rank):
    deck = Deck()
    deck.set_description(suit, "[red]Literal[/red]")
    target = next(card for card in deck.cards if card.suit == suit and card.rank == rank)
    deck = Deck(
        cards=tuple(card for card in deck.cards if card != target),
        dealt=(target,),
        descriptions=deck.descriptions,
    )
    console = Console(width=50, color_system=None)
    with console.capture() as capture:
        console.print(card_art(deck))
    rendered = capture.get()
    assert str(target) in rendered
    assert suit.symbol in rendered
    assert "[red]Literal[/red]" in rendered


def test_dealer_entry_points_and_stylesheet():
    with patch("huckdeck.cli.HuckDeck") as app:
        main([])
    app.return_value.run.assert_called_once_with()
    with patch("huckdeck.cli.main") as launcher:
        runpy.run_module("huckdeck", run_name="__main__")
    launcher.assert_called_once_with()
    with patch("huckdeck.cli.main") as launcher:
        runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "huckdeck.py"), run_name="__main__"
        )
    launcher.assert_called_once_with()
    entry = next(
        point for point in distribution("huckdeck").entry_points if point.name == "huckdeck"
    )
    assert entry.load() is main
    assert files("huckdeck.ui").joinpath("dealer.tcss").is_file()


def test_dealer_starts_shuffled_outside_checkout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        app = HuckDeck(rng=Random(9))
        assert app.deck.cards != Deck().cards
        async with app.run_test() as pilot:
            await pilot.click("#deal-card")
            assert len(app.deck.dealt) == 1

    asyncio.run(scenario())
