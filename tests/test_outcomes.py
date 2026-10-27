import asyncio

import pytest
from helpers import ScriptedRandom, start_game
from textual.color import Color
from textual.widgets import Static

from wid.formatting import dice_parts, summarize
from wid.rolls import Outcome
from wid.ui.app import RollerApp
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


@pytest.mark.ui
def test_changing_theme_recolours_the_shown_result_without_changing_its_text():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 4, 6, 6]))
        async with app.run_test(size=(120, 50)) as pilot:
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            await pilot.pause()
            dice = app.query_one("#dice", Static)
            before_text = str(dice.content)
            before_colours = {s.style.color for s in dice.render_line(0) if s.style}

            app.theme = "dracula" if app.theme != "dracula" else "nord"
            await pilot.pause()

            after_colours = {s.style.color for s in dice.render_line(0) if s.style}
            assert str(dice.content) == before_text
            assert after_colours != before_colours

    asyncio.run(scenario())
