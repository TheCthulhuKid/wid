from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Genre(StrEnum):
    CORE = "core"
    HECKBOY = "heckboy"
    SECOND_CONTACT = "second_contact"
    OLDHEART = "oldheart"
    BALL_SEASON = "ball_season"
    THIS_ISNT_HAPPENING = "this_isnt_happening"


class Recovers(StrEnum):
    """What a kit's recovery after a Danger gives back, where the kit states an amount."""

    STRAIN = "strain"
    RESOURCES = "resources"


class WiDProfile(BaseModel):
    """Display metadata and explicit kit capabilities."""

    model_config = ConfigDict(frozen=True)

    genre: Genre
    name: str
    attributes: tuple[str, ...] = ("Athleticism", "Composure", "Reasoning")
    # Strain boxes before each wound on the tracker; Heckboy wounds on the fifth strain.
    strain_per_wound: int = 3
    uses_items: bool = True
    has_powers: bool = False
    has_tech: bool = False
    has_rerolls: bool = False
    has_standing: bool = False
    has_resources: bool = False
    # The scene trackers a kit gives the GM.
    has_barricade: bool = False
    has_revelations: bool = False
    # Recovery after a Danger, where the kit's text gives the amount (the base game's is unknown).
    recovers: Recovers | None = None
    # The kit's highlight on light paper and on dark paper (the browser's dark colours).
    highlight: str = "#B22222"
    dark_highlight: str = "#EF6A63"


PROFILES = {
    Genre.CORE: WiDProfile(genre=Genre.CORE, name="Core WiD"),
    Genre.HECKBOY: WiDProfile(
        genre=Genre.HECKBOY,
        name="Heckboy",
        attributes=("Aberrance", "Ferocity", "Savvy"),
        strain_per_wound=4,
        has_powers=True,
        recovers=Recovers.STRAIN,
        highlight="#D94F00",
        dark_highlight="#FF8A4C",
    ),
    Genre.SECOND_CONTACT: WiDProfile(
        genre=Genre.SECOND_CONTACT,
        name="Second Contact",
        attributes=("Science", "Culture", "Muscle"),
        # Tech replaces items in this kit.
        uses_items=False,
        has_tech=True,
        highlight="#0072B2",
        dark_highlight="#5AB4F0",
    ),
    Genre.OLDHEART: WiDProfile(
        genre=Genre.OLDHEART,
        name="Oldheart",
        attributes=("Depravity", "Hospitality", "Fitness"),
        has_rerolls=True,
        has_revelations=True,
        highlight="#3B2230",
        dark_highlight="#C99AB5",
    ),
    Genre.BALL_SEASON: WiDProfile(
        genre=Genre.BALL_SEASON,
        name="Ball Season",
        attributes=("Propriety", "Stoutness", "Yearning"),
        has_standing=True,
        highlight="#246F3C",
        dark_highlight="#5CBF7A",
    ),
    Genre.THIS_ISNT_HAPPENING: WiDProfile(
        genre=Genre.THIS_ISNT_HAPPENING,
        name="This Isn't Happening",
        attributes=("Instincts", "Endurance", "Charity"),
        has_resources=True,
        has_barricade=True,
        recovers=Recovers.RESOURCES,
        highlight="#6E5015",
        dark_highlight="#D2A85A",
    ),
}
