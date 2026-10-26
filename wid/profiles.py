from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Genre(StrEnum):
    CORE = "core"
    HECKBOY = "heckboy"
    SECOND_CONTACT = "second_contact"
    OLDHEART = "oldheart"
    BALL_SEASON = "ball_season"
    THIS_ISNT_HAPPENING = "this_isnt_happening"


class WiDProfile(BaseModel):
    """Display metadata and explicit kit capabilities."""

    model_config = ConfigDict(frozen=True)

    genre: Genre
    name: str
    attributes: tuple[str, ...] = ("Athleticism", "Composure", "Reasoning")
    uses_items: bool = True
    has_powers: bool = False
    has_tech: bool = False
    has_rerolls: bool = False
    has_standing: bool = False
    has_resources: bool = False


PROFILES = {
    Genre.CORE: WiDProfile(genre=Genre.CORE, name="Core WiD"),
    Genre.HECKBOY: WiDProfile(
        genre=Genre.HECKBOY,
        name="Heckboy",
        attributes=("Aberrance", "Ferocity", "Savvy"),
        has_powers=True,
    ),
    Genre.SECOND_CONTACT: WiDProfile(
        genre=Genre.SECOND_CONTACT,
        name="Second Contact",
        attributes=("Science", "Culture", "Muscle"),
        # Tech replaces items in this kit.
        uses_items=False,
        has_tech=True,
    ),
    Genre.OLDHEART: WiDProfile(
        genre=Genre.OLDHEART,
        name="Oldheart",
        attributes=("Depravity", "Hospitality", "Fitness"),
        has_rerolls=True,
    ),
    Genre.BALL_SEASON: WiDProfile(
        genre=Genre.BALL_SEASON,
        name="Ball Season",
        attributes=("Propriety", "Stoutness", "Yearning"),
        has_standing=True,
    ),
    Genre.THIS_ISNT_HAPPENING: WiDProfile(
        genre=Genre.THIS_ISNT_HAPPENING,
        name="This Isn't Happening",
        attributes=("Instincts", "Endurance", "Charity"),
        has_resources=True,
    ),
}
