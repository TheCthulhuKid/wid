import asyncio

import pytest
from helpers import change_genre, click, start_game, text
from textual.widgets import Collapsible

from wid.dangers import Difficulty
from wid.game import Game
from wid.profiles import Genre
from wid.rolls import LOCKED_NOTE, NOT_READY_NOTE, StrainTracker
from wid.ui.app import RollerApp
from wid.ui.widgets import StrainBox


def test_strain_fills_in_order_up_to_defeat():
    assert StrainTracker().take(5).boxes == (True,) * 5 + (False,) * 7
    assert not StrainTracker().take(11).defeated
    assert StrainTracker().take(15).defeated


def test_a_wound_needs_the_strain_before_it_and_then_locks_it():
    assert StrainTracker().lock_reason(3) == NOT_READY_NOTE
    tracker = StrainTracker().take(4)
    assert tracker.lock_reason(0) == LOCKED_NOTE
    assert tracker.lock_reason(3) is None
    with pytest.raises(ValueError, match="stay marked"):
        tracker.set_box(0, False)
    assert not tracker.set_box(3, False).locked_boxes


def test_take_wound_fills_the_row():
    assert StrainTracker().take(1).take_wound().boxes == (True,) * 4 + (False,) * 8
    with pytest.raises(ValueError, match="Defeat is already marked"):
        StrainTracker().take(12).take_wound()
    game = Game()
    game.session.strain = StrainTracker().take(12)
    with pytest.raises(ValueError, match="Defeat is already marked"):
        game.take_strain()


def test_recovery_after_a_danger_gives_back_what_the_kit_says():
    heckboy = Game()
    heckboy.change_kit(Genre.HECKBOY)
    heckboy.start_game((1, 2, 3))
    heckboy.session.strain = heckboy.session.strain.take(6)
    assert heckboy.recover_after(Difficulty.BOSS) == (
        "Recovery after a Boss Danger — cleared 1 strain: 4 strain, 1 wound."
    )
    assert heckboy.undo() == "Undid the last recovery."

    survivor = Game()
    survivor.change_kit(Genre.THIS_ISNT_HAPPENING)
    survivor.start_game((1, 2, 3))
    assert survivor.recover_after(Difficulty.MEGA) == (
        "Recovery after a Mega Danger — Resources +3: 6 in the pool."
    )
    assert survivor.recover_after(Difficulty.COMPETENT).endswith(
        "Resources +0: 6 in the pool. The pool holds at most 6."
    )
    with pytest.raises(ValueError, match="does not say how much"):
        Game().recover_after(Difficulty.BOSS)


@pytest.mark.ui
def test_strain_buttons_and_locked_boxes():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 45)) as pilot:
            await start_game(app, pilot)
            wound = app.query_one("#strain-wound-0", StrainBox)
            assert wound.disabled
            assert not app.query_one("#strain-box-0-3", StrainBox).display
            await click(app, pilot, "#take-strain")
            assert app.session.strain.boxes[0]
            await click(app, pilot, "#take-wound")
            assert app.session.strain.boxes == (True,) * 4 + (False,) * 8
            title = app.query_one("#strain-section", Collapsible).title
            assert title == "Strain tracker: 3 strain, 1 wound"
            assert app.query_one("#strain-box-0-1", StrainBox).disabled
            app.query_one("#strain-wound-1", StrainBox).value = True
            await pilot.pause()
            assert not app.session.strain.boxes[7]
            assert text(app, "#feedback") == NOT_READY_NOTE
            await change_genre(app, pilot, Genre.HECKBOY)
            assert app.query_one("#strain-box-0-3", StrainBox).display

    asyncio.run(scenario())
