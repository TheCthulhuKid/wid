"""Result text coloured by outcome, with colours checked against the theme background."""

from textual.color import Color
from textual.content import Content
from textual.style import Style

from wid.formatting import Part, dice_parts, summary_parts
from wid.rolls import Outcome, RollResult

# WCAG minimum for large text and interface parts. The outcome words are bold and always
# spelled out, so colour is never the only signal.
MIN_CONTRAST = 3.0
STEP = 0.05

OUTCOME_VARIABLES = {
    Outcome.HIT: "text-success",
    Outcome.MISS: "text-warning",
    Outcome.FUMBLE: "text-error",
}


def luminance(color: Color) -> float:
    def channel(value: int) -> float:
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b)


def contrast_ratio(first: Color, second: Color) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def opaque(value: str, background: Color) -> Color:
    color = Color.parse(value)
    return background.blend(color, color.a) if color.a < 1 else color


def readable(color: Color, background: Color) -> Color:
    """``color``, moved away from ``background`` only as far as needed to be readable."""
    shift = Color.darken if luminance(background) > 0.5 else Color.lighten
    amount = 0.0
    while contrast_ratio(color, background) < MIN_CONTRAST and amount < 1:
        amount += STEP
        color = shift(color, STEP)
    return color


def outcome_styles(variables: dict[str, str]) -> dict[Outcome, Style]:
    """Bold styles per outcome from the active theme's CSS variables."""
    # The result panel is drawn on the theme's surface colour.
    background = Color.parse(variables["surface"])
    return {
        outcome: Style(
            foreground=readable(opaque(variables[name], background), background), bold=True
        )
        for outcome, name in OUTCOME_VARIABLES.items()
    }


def _content(parts: list[Part], styles: dict[Outcome, Style]) -> Content:
    return Content.assemble(
        *(text if outcome is None else (text, styles[outcome]) for text, outcome in parts)
    )


def dice_content(result: RollResult, variables: dict[str, str]) -> Content:
    styles = outcome_styles(variables)
    return Content("\n").join(_content(line, styles) for line in dice_parts(result))


def summary_content(result: RollResult, variables: dict[str, str]) -> Content:
    return _content(summary_parts(result), outcome_styles(variables))
