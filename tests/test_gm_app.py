import asyncio

import pytest
from helpers import ScriptedRandom, click, text
from textual.widgets import DataTable, Input, Select

from wid.dangers import Complexity, DangerClass, Difficulty
from wid.formatting import NO_DANGER_HINT
from wid.profiles import Genre
from wid.ui.gm_app import GmApp

pytestmark = pytest.mark.ui


def test_a_danger_is_added_activated_removed_and_kept_across_a_kit_change():
    async def scenario():
        app = GmApp(rng=ScriptedRandom([4, 2, 5]))
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            await click(app, pilot, "#load-session")
            await pilot.click("#cancel-load")
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            assert [kind for _, kind in app.query_one("#danger-class", Select)._options][-1] == (
                DangerClass.TITAN
            )
            app.query_one("#new-danger-name", Input).value = "Zeus"
            app.query_one("#danger-class", Select).value = DangerClass.TITAN
            app.query_one("#difficulty", Select).value = Difficulty.MEGA
            await click(app, pilot, "#add-danger")
            summary = "Zeus: Mega Titan — threshold 16, 2 hits to pass"
            assert text(app, "#danger-summary-0") == summary
            assert app.query_one("#new-danger-name", Input).value == ""
            assert app.query_one("#loadout", DataTable).row_count == 6

            await pilot.press("ctrl+r")
            assert text(app, "#activation").startswith("Activation (4, 2, 5): Dominate")
            await click(app, pilot, "#commit-hits")
            assert "progress 1" in text(app, "#scene-summary")
            app.query_one("#task", Select).value = Complexity.HIGH
            await click(app, pilot, "#task-strain")
            assert text(app, "#feedback") == "High task: 12 strain for 4 PCs to share."

            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            assert app.screen.query_one("#save-first")
            await pilot.click("#keep-scene")
            await pilot.pause()
            assert text(app, "#feedback") == "Kit changed to Core WiD. Dropped Zeus."
            assert text(app, "#scene-summary") == NO_DANGER_HINT
            await click(app, pilot, "#undo")
            assert app.game.genre == Genre.HECKBOY
            assert app.query_one("#genre", Select).value == Genre.HECKBOY
            await click(app, pilot, "#remove-danger-0")
            assert text(app, "#feedback") == "Removed Zeus."
            assert not app.query_one("#danger-row-0").display
            # A kit's tracker shows in that kit only.
            app.query_one("#genre", Select).value = Genre.THIS_ISNT_HAPPENING
            await pilot.pause()
            await pilot.click("#keep-scene")
            await pilot.pause()
            assert app.query_one("#barricade-row").display
            assert not app.query_one("#revelations-field").display
            await click(app, pilot, "#barricade-up")
            assert text(app, "#feedback") == "Barricade +1: barricade 1 of 6."
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#keep-scene")
            await pilot.pause()
            assert not app.query_one("#barricade-row").display
            assert app.game.scene.barricade == 0

    asyncio.run(scenario())
