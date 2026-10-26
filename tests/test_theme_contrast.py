import asyncio

from helpers import reveal
from rich.color import Color as RichColor
from test_rollerapp import start_game
from test_rolls import ScriptedRandom
from textual.color import Color

from wid.ui.app import RollerApp
from wid.ui.outcomes import MIN_CONTRAST, contrast_ratio

OUTCOME_TEXT = {"hit", "miss", "fumble"}
SUMMARY_TEXT = ("Hits:", "Misses:", "Fumbles:")


def rendered_contrast(foreground: RichColor, background: RichColor) -> float:
    return contrast_ratio(Color(*foreground.get_truecolor()), Color(*background.get_truecolor()))


def coloured_words(widget, words):
    """(text, foreground, background) for each rendered segment starting with one of words."""
    found = []
    for y in range(widget.size.height):
        for segment in widget.render_line(y):
            style = segment.style
            if segment.text.strip().startswith(tuple(words)) and style and style.color:
                found.append((segment.text.strip(), style.color, style.bgcolor))
    return found


def themes():
    names = sorted(RollerApp().available_themes)
    # The ansi themes use the terminal's own palette, so their contrast is not ours to judge.
    return [name for name in names if not name.startswith("ansi-")]


BUTTONS = ("#roll-attribute-0", "#take-strain", "#save-session")


def assert_readable(words, *context):
    assert words, context
    for text, foreground, background in words:
        assert rendered_contrast(foreground, background) >= MIN_CONTRAST, (*context, text)


def test_outcomes_and_action_buttons_are_readable_in_every_theme():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 4, 6, 6]))
        async with app.run_test(size=(120, 50)) as pilot:
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            for theme in themes():
                app.theme = theme
                app.show_result(app.session.current_result)
                await pilot.pause()
                dice = coloured_words(app.query_one("#dice"), OUTCOME_TEXT)
                assert {text for text, *_ in dice} == OUTCOME_TEXT, theme
                assert_readable(dice, theme)
                assert_readable(coloured_words(app.query_one("#summary"), SUMMARY_TEXT), theme)
                for selector in BUTTONS:
                    button = await reveal(app, pilot, selector)
                    words = coloured_words(button, str(button.label).split())
                    assert_readable(words, theme, selector)

    asyncio.run(scenario())
