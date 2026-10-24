from wid.formatting import (
    attribute_label,
    describe_dice,
    dice_lines,
    resources_line,
    summarize,
)
from wid.profiles import Genre


def test_dice_formats_differ_only_in_verbosity(saved_session_factory):
    result = saved_session_factory().session.current_result

    first_long = describe_dice(result).splitlines()[0]
    first_short = dice_lines(result).splitlines()[0]

    assert first_long.startswith("Die 1: raw ")
    assert first_short.startswith("1: ")
    assert len(describe_dice(result).splitlines()) == len(dice_lines(result).splitlines())
    assert first_long.endswith(first_short.rsplit(" ", 1)[1])


def test_summary_and_attribute(saved_session_factory):
    result = saved_session_factory().session.current_result

    assert summarize(result).startswith("Hits: ")
    assert "expertise 1" in summarize(result)
    assert attribute_label(result) == "Athleticism (rank 1)"


def test_resources_line_by_kit(saved_session_factory):
    heckboy = saved_session_factory(Genre.HECKBOY).session
    line = resources_line(
        heckboy.current_result, total_strain=1, total_corruption=0, tech_remaining=None
    )
    assert line == "Strain: +1 (session 1)"

    oldheart = saved_session_factory(Genre.OLDHEART).session
    line = resources_line(
        oldheart.current_result, total_strain=0, total_corruption=1, tech_remaining=3
    )
    assert line == "Strain: +0 (session 0) | Corruption: +1 (session 1) | Tech remaining: 3"
