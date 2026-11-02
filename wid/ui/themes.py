"""The danger theme: cream paper, charcoal labels, lavender fields, the kit's highlight."""

from textual.theme import Theme

from wid.profiles import PROFILES, Genre

DANGER_THEME = "danger"
# Fumbles and errors stay red in every kit; only the highlight follows the kit.
RED = "#B22222"


def danger_theme(genre: Genre) -> Theme:
    """The danger theme in ``genre``'s highlight colour."""
    highlight = PROFILES[genre].highlight
    return Theme(
        name=DANGER_THEME,
        primary=highlight,
        secondary="#2F2D2D",
        accent=highlight,
        warning="#8A5A00",
        error=RED,
        success="#2E7D4F",
        foreground="#2B2929",
        background="#FBF8F1",
        surface="#E6E3EC",
        panel="#DAD7E2",
        dark=False,
        variables={"footer-key-foreground": highlight},
    )
