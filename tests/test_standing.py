import asyncio

import pytest
from helpers import change_genre, reveal

from wid.profiles import Genre
from wid.rolls import standing_label
from wid.sessions import SavedSession
from wid.ui.app import RollerApp
from wid.ui.widgets import StandingTrack


def test_standing_starts_reputable_and_stays_on_the_track(session_factory):
    session = session_factory(Genre.BALL_SEASON)
    assert standing_label(session.standing) == "Reputable"
    labels = [standing_label(index) for index in range(5)]
    assert labels == ["Esteemed", "Reputable", "Reputable", "Reputable", "Scandalous"]
    assert session.set_standing(4) == 4
    for outside in (-1, 5):
        with pytest.raises(ValueError, match="runs from Esteemed"):
            session.set_standing(outside)
    assert session.standing == 4
    with pytest.raises(ValueError, match="Core WiD has no Standing"):
        session_factory().set_standing(0)


def test_standing_belongs_to_ball_season(saved_session_factory):
    data = saved_session_factory().model_dump()
    data["session"]["standing"] = 0
    with pytest.raises(ValueError, match="Only Ball Season can have Standing"):
        SavedSession.model_validate(data)


@pytest.mark.ui
def test_track_moves_by_keys_and_clicks_for_ball_season_only():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(120, 50)) as pilot:
            assert not app.query_one("#standing-field").display
            await change_genre(app, pilot, Genre.BALL_SEASON)
            track = await reveal(app, pilot, "#standing")
            assert str(track.render()) == "○ ○ ● ○ ○  Reputable"
            track.focus()
            await pilot.press("left", "left")
            assert app.session.standing == 0
            assert str(track.render()) == "● ○ ○ ○ ○  Esteemed"
            await pilot.press("left")
            assert app.session.standing == 0
            assert "runs from Esteemed" in str(app.query_one("#feedback").content)
            await pilot.click(StandingTrack, offset=(8, 0))
            assert app.session.standing == 4
            assert str(track.render()).endswith("Scandalous")
            await change_genre(app, pilot, Genre.CORE)
            assert not app.query_one("#standing-field").display
            assert track.standing == 2

    asyncio.run(scenario())
