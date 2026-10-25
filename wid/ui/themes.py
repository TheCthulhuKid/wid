"""The danger theme: cream paper, charcoal labels, lavender fields, red highlights."""

from textual.theme import Theme

DANGER_THEME = "danger"
HIGHLIGHT = "#B22222"

DANGER = Theme(
    name=DANGER_THEME,
    primary=HIGHLIGHT,
    secondary="#2F2D2D",
    accent=HIGHLIGHT,
    warning="#8A5A00",
    error=HIGHLIGHT,
    success="#2E7D4F",
    foreground="#2B2929",
    background="#FBF8F1",
    surface="#E6E3EC",
    panel="#DAD7E2",
    dark=False,
    variables={"footer-key-foreground": HIGHLIGHT},
)
