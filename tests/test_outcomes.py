import pytest
from textual.color import Color

from wid.formatting import dice_parts, summarize
from wid.rolls import Outcome
from wid.ui.outcomes import (
    MIN_CONTRAST,
    contrast_ratio,
    dice_content,
    opaque,
    outcome_styles,
    readable,
    summary_content,
)

WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)


def test_contrast_of_black_and_white_is_the_maximum():
    assert contrast_ratio(BLACK, WHITE) == pytest.approx(21)
    assert contrast_ratio(WHITE, WHITE) == pytest.approx(1)


def test_readable_colour_is_left_alone():
    color = Color(0, 100, 0)

    assert readable(color, WHITE) == color


@pytest.mark.parametrize("background", [WHITE, BLACK])
def test_unreadable_colour_moves_away_from_the_background(background):
    faint = Color(180, 180, 100) if background == WHITE else Color(60, 60, 20)

    result = readable(faint, background)

    assert contrast_ratio(faint, background) < MIN_CONTRAST
    assert contrast_ratio(result, background) >= MIN_CONTRAST


def test_transparent_colour_is_composited_on_the_background():
    assert opaque("rgba(255,0,0,0)", WHITE) == WHITE
    assert opaque("#112233", WHITE) == Color(17, 34, 51)


def test_styles_cover_every_outcome():
    variables = {
        "surface": "#FFFFFF",
        "text-success": "#00AA00",
        "text-warning": "#AAAA00",
        "text-error": "#AA0000",
    }

    assert set(outcome_styles(variables)) == set(Outcome)


def test_coloured_text_is_the_same_text_the_log_uses(saved_session_factory):
    result = saved_session_factory().session.current_result
    variables = {
        "surface": "#222222",
        "text-success": "#00FF00",
        "text-warning": "#FFFF00",
        "text-error": "#FF0000",
    }

    lines = ("".join(text for text, _ in line) for line in dice_parts(result))
    assert dice_content(result, variables).plain == "\n".join(lines)
    assert summary_content(result, variables).plain == summarize(result)
