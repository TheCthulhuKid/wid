from random import Random
from typing import ClassVar

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Static

from huckdeck.deck import Deck, Rank, Suit
from huckdeck.ui.dialogs import ConfirmShuffle


def card_art(deck: Deck) -> Panel:
    card = deck.current_card
    if card is None:
        return Panel(Text("Ready to deal\n♥  ♦  ♣  ♠", justify="center"), title="Current card")
    color = "red" if card.suit in (Suit.HEARTS, Suit.DIAMONDS) else "cyan"
    face = Text(
        f"{card.rank:<9}\n\n{card.suit.symbol:^9}\n\n{card.rank:>9}",
        style=f"bold {color}",
        justify="center",
    )
    return Panel(face, title=Text(str(card)), subtitle=Text(deck.description_for(card.suit)))


class HuckDeck(App):
    """Deal a 56-card deck with suited jokers and a separate dealt-ace tracker."""

    CSS_PATH = "dealer.tcss"
    TITLE = "HuckDeck"
    BINDINGS: ClassVar = [
        ("ctrl+d", "deal", "Deal"),
        ("ctrl+s", "shuffle", "Restore & shuffle"),
        ("d", "toggle_dark", "Theme"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, *, deck: Deck | None = None, rng: Random | None = None):
        super().__init__()
        self.rng = rng if rng is not None else Random()
        self.deck = deck if deck is not None else Deck()
        if deck is None:
            self.deck.shuffle(rng=self.rng)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="dealer-layout"):
            with VerticalScroll(id="draw-panel"):
                yield Static(id="current-card", markup=False)
                yield Static(id="card-count", markup=False)
                yield Button("Deal", id="deal-card", variant="primary")
                yield Static("Aces and jokers automatically draw another card.")
                yield Button("Restore & shuffle", id="shuffle-deck", variant="warning")
                yield Static("Shuffle returns all dealt cards and clears aces.")
                yield Static(id="dealer-status", markup=False)
                yield Label("Dealt aces")
                yield Static(id="ace-tracker", markup=False)
            with VerticalScroll(id="deck-panel"):
                yield Label("Suit descriptions (kept when shuffling)")
                for suit in Suit:
                    yield Label(f"{suit.symbol} {suit}")
                    yield Input(
                        value=self.deck.description_for(suit),
                        placeholder=f"Description for {suit}",
                        id=f"description-{suit.name.lower()}",
                    )
                yield Label("Cards remaining — grouped by suit, not draw order")
                yield Static(id="remaining-cards", markup=False)
                yield Label("Dealt cards — oldest first")
                yield Static(id="dealt-cards", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_deck()

    def refresh_deck(self) -> None:
        self.query_one("#current-card", Static).update(card_art(self.deck))
        self.query_one("#card-count", Static).update(
            f"{len(self.deck.cards)} left / 56 · {len(self.deck.dealt)} dealt"
        )
        self.query_one("#deal-card", Button).disabled = not self.deck.cards
        aces = {card.suit for card in self.deck.aces}
        self.query_one("#ace-tracker", Static).update(
            f"{len(aces)} / 4 aces dealt\n"
            + "\n".join(
                f"{'●' if suit in aces else '○'} A{suit.symbol} {suit}: "
                f"{'dealt' if suit in aces else 'in deck'}"
                for suit in Suit
            )
        )
        remaining = {(card.suit, card.rank) for card in self.deck.cards}
        self.query_one("#remaining-cards", Static).update(
            "\n\n".join(
                f"{suit.symbol} {suit}: "
                + (" ".join(rank for rank in Rank if (suit, rank) in remaining) or "—")
                for suit in Suit
            )
        )
        self.query_one("#dealt-cards", Static).update(
            " · ".join(f"{card.rank}{card.suit.symbol}" for card in self.deck.dealt) or "None yet"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id and event.input.id.startswith("description-"):
            suit = Suit[event.input.id.removeprefix("description-").upper()]
            self.deck.set_description(suit, event.value)
            self.query_one("#current-card", Static).update(card_art(self.deck))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "deal-card":
            self.action_deal()
        elif event.button.id == "shuffle-deck":
            self.action_shuffle()

    def action_deal(self) -> None:
        if len(self.screen_stack) > 1:
            return
        try:
            cards = self.deck.draw_chain()
        except ValueError as error:
            self.query_one("#dealer-status", Static).update(str(error))
            return
        self.refresh_deck()
        status = "Dealt " + " → ".join(str(card) for card in cards)
        if not self.deck.cards:
            status += ". Deck exhausted; shuffle to restore all 56 cards."
        self.query_one("#dealer-status", Static).update(status)

    def action_shuffle(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self.deck.dealt:
            self.push_screen(
                ConfirmShuffle(),
                self.finish_shuffle,
            )
            return
        self.finish_shuffle(True)

    def finish_shuffle(self, confirmed: bool) -> None:
        if not confirmed:
            return
        self.deck.shuffle(rng=self.rng)
        self.refresh_deck()
        self.query_one("#dealer-status", Static).update("All 56 cards restored and shuffled.")

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"
