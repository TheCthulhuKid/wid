import asyncio

import pytest
from helpers import click, start_game, text
from textual.widgets import Collapsible

from wid.game import Game
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


@pytest.mark.ui
def test_strain_buttons_and_locked_boxes():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 45)) as pilot:
            await start_game(app, pilot)
            wound = app.query_one("#strain-box-3", StrainBox)
            assert wound.disabled
            await click(app, pilot, "#take-strain")
            assert app.session.strain.boxes[0]
            await click(app, pilot, "#take-wound")
            assert app.session.strain.boxes == (True,) * 4 + (False,) * 8
            title = app.query_one("#strain-section", Collapsible).title
            assert title == "Strain tracker: 3 strain, 1 wound"
            assert app.query_one("#strain-box-1", StrainBox).disabled
            app.query_one("#strain-box-7", StrainBox).value = True
            await pilot.pause()
            assert not app.session.strain.boxes[7]
            assert text(app, "#feedback") == NOT_READY_NOTE

    asyncio.run(scenario())
