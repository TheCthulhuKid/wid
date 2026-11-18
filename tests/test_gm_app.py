import asyncio

import pytest
from helpers import ScriptedRandom, click, text
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Input,
    Select,
    TabbedContent,
    TextArea,
)

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
            assert app.query_one("#reference-section", Collapsible).collapsed
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            assert app.query_one("#class-reference", DataTable).get_row_at(4)[0] == "Titan"
            assert [kind for _, kind in app.query_one("#danger-class", Select)._options][-1] == (
                DangerClass.TITAN
            )
            assert app.query_one("#raise-threshold", Button).disabled
            app.query_one("#new-danger-name", Input).value = "Zeus"
            app.query_one("#danger-class", Select).value = DangerClass.TITAN
            app.query_one("#difficulty", Select).value = Difficulty.MEGA
            await click(app, pilot, "#add-danger")
            summary = "Zeus: Mega Titan — threshold 16, 2 hits to pass"
            assert text(app, "#danger-summary-0") == summary
            assert app.query_one("#new-danger-name", Input).value == ""
            assert app.query_one("#loadout", DataTable).row_count == 6
            assert text(app, "#loadout-heading") == "Loadout: Zeus (Mega Titan)"
            assert not app.query_one("#acting-row").display

            await pilot.press("ctrl+r")
            assert text(app, "#activation").startswith("Zeus (Mega Titan) activates (4, 2, 5)")
            await click(app, pilot, "#commit-hits")
            assert "progress 1" in text(app, "#scene-summary")
            # A second Danger offers the choice of whose loadout to roll on.
            app.query_one("#danger-class", Select).value = DangerClass.BRUTE
            app.query_one("#difficulty", Select).value = Difficulty.HEAVY
            await click(app, pilot, "#add-danger")
            assert app.query_one("#acting-row").display
            app.query_one("#acting", Select).value = 1
            await pilot.pause()
            assert text(app, "#loadout-heading") == "Loadout: Danger 2 (Heavy Brute)"
            await click(app, pilot, "#remove-danger-1")
            assert text(app, "#loadout-heading") == "Loadout: Zeus (Mega Titan)"
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


def test_the_scenario_tab_edits_the_sheet():
    async def scenario():
        app = GmApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.query_one("#genre").focus()
            await pilot.press("a")
            assert app.query_one("#details", TabbedContent).active == "tab-scenario"
            app.query_one("#waypoints-3", Input).value = "The old bus depot"
            app.query_one("#new-scenario-danger-name", Input).value = "Colossus"
            await click(app, pilot, "#add-scenario-danger")
            assert app.game.scenario.waypoints[3] == "The old bus depot"
            summary = "Colossus: Heavy Brute — threshold 8, 1 hit to pass"
            assert text(app, "#scenario-danger-summary-0") == summary
            app.query_one("#pc-count", Select).value = 3
            await pilot.pause()
            assert "threshold 6" in text(app, "#scenario-danger-summary-0")
            app.query_one("#scenario-danger-difficulty-0", Select).value = Difficulty.MEGA
            await pilot.pause()
            assert app.game.scenario.dangers[0].difficulty == Difficulty.MEGA

    asyncio.run(scenario())


def test_the_scene_tab_starts_a_scene_from_the_scenario():
    async def scenario():
        app = GmApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            assert not app.query_one("#start-scene-row").display
            app.query_one("#new-scenario-danger-name", Input).value = "Colossus"
            await click(app, pilot, "#add-scenario-danger")
            app.query_one("#scenario-danger-description-0", TextArea).load_text("Wades ashore.")
            app.query_one("#new-scenario-danger-name", Input).value = "Moth Choir"
            await click(app, pilot, "#add-scenario-danger")
            await pilot.press("e")
            await click(app, pilot, "#start-scene")
            assert text(app, "#scene-danger-text") == "Wades ashore."
            assert app.query_one("#end-scene", Button).disabled
            app.query_one("#amount", Select).value = 6
            await click(app, pilot, "#commit-hits")
            await click(app, pilot, "#commit-hits")
            assert not app.query_one("#end-scene", Button).disabled
            await click(app, pilot, "#end-scene")
            assert app.query_one("#scenario-scene", Select).value == 1

    asyncio.run(scenario())


def test_importing_a_file_of_two_scenarios_asks_which(tmp_path):
    path = tmp_path / "sheets.md"
    path.write_text("# One\n\n### Bear\n*Heavy Brute*\n\n# Two\n\n### Wolf\n*Boss Swarm*\n")

    async def scenario():
        app = GmApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.query_one("#scenario-path", Input).value = str(path)
            await click(app, pilot, "#import-scenario")
            await pilot.click("#scenario-1")
            await pilot.pause()
            assert text(app, "#feedback") == "Imported the scenario Two."
            assert text(app, "#scenario-danger-summary-0").startswith("Wolf: Boss Swarm")

    asyncio.run(scenario())
