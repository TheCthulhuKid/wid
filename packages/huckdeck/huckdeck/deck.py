from enum import StrEnum
from random import Random
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Suit(StrEnum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"

    @property
    def symbol(self) -> str:
        return {Suit.HEARTS: "♥", Suit.DIAMONDS: "♦", Suit.CLUBS: "♣", Suit.SPADES: "♠"}[self]


class Rank(StrEnum):
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    JOKER = "Joker"


class Card(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        return f"{self.rank} of {self.suit}"


class SuitDescription(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suit: Suit
    description: str = ""


def standard_cards() -> tuple[Card, ...]:
    return tuple(Card(suit=suit, rank=rank) for suit in Suit for rank in Rank)


class Deck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cards: tuple[Card, ...] = Field(default_factory=standard_cards)
    dealt: tuple[Card, ...] = ()
    descriptions: tuple[SuitDescription, ...] = Field(
        default_factory=lambda: tuple(SuitDescription(suit=suit) for suit in Suit)
    )

    @model_validator(mode="after")
    def validate_deck(self) -> Self:
        identities = [(card.suit, card.rank) for card in (*self.cards, *self.dealt)]
        expected = {(suit, rank) for suit in Suit for rank in Rank}
        if len(identities) != len(expected) or set(identities) != expected:
            raise ValueError("The deck must contain each of the 56 suited cards exactly once")
        if len(self.descriptions) != len(Suit) or {item.suit for item in self.descriptions} != set(
            Suit
        ):
            raise ValueError("Each suit must have exactly one description")
        return self

    @property
    def aces(self) -> tuple[Card, ...]:
        return tuple(card for card in self.dealt if card.rank == Rank.ACE)

    @property
    def current_card(self) -> Card | None:
        return self.dealt[-1] if self.dealt else None

    def description_for(self, suit: Suit) -> str:
        suit = Suit(suit)
        return next(item.description for item in self.descriptions if item.suit == suit)

    def set_description(self, suit: Suit, description: str) -> None:
        suit = Suit(suit)
        updated = tuple(
            SuitDescription(suit=suit, description=description) if item.suit == suit else item
            for item in self.descriptions
        )
        object.__setattr__(self, "descriptions", updated)

    def shuffle(self, *, rng: Random | None = None) -> None:
        cards = [*self.cards, *self.dealt]
        (rng if rng is not None else Random()).shuffle(cards)
        candidate = Deck(cards=tuple(cards), descriptions=self.descriptions)
        object.__setattr__(self, "cards", candidate.cards)
        object.__setattr__(self, "dealt", candidate.dealt)

    def draw(self) -> Card:
        return self.deal(1)[0]

    def draw_chain(self) -> list[Card]:
        """Deal until an ordinary card is reached or the remaining deck runs out."""
        count = 0
        for card in self.cards:
            count += 1
            if card.rank not in (Rank.ACE, Rank.JOKER):
                break
        return self.deal(count or 1)

    def deal(self, num_cards: int) -> list[Card]:
        if type(num_cards) is not int or num_cards < 1:
            raise ValueError("Deal count must be a positive integer")
        if num_cards > len(self.cards):
            raise ValueError("Not enough cards left; shuffle to restore the full deck")
        drawn = self.cards[:num_cards]
        candidate = Deck(
            cards=self.cards[num_cards:],
            dealt=(*self.dealt, *drawn),
            descriptions=self.descriptions,
        )
        object.__setattr__(self, "cards", candidate.cards)
        object.__setattr__(self, "dealt", candidate.dealt)
        return list(drawn)
