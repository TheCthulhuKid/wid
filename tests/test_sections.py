import asyncio

import pytest
from helpers import click, start_game
from textual.widgets import Collapsible

from wid.formatting import strain_summary
from wid.rolls import StrainTracker
from wid.ui.app import RollerApp


def run(scenario, rng=None, size=(100, 45)):
    async def main():
        app = RollerApp(rng=rng)
        async with app.run_test(size=size) as pilot:
            await scenario(app, pilot)

    asyncio.run(main())


def section(app, name):
    return app.query_one(f"#{name}-section", Collapsible)


def test_summary_text():
    assert strain_summary(StrainTracker()) == "Strain tracker: 0 strain, 0 wounds"
    assert strain_summary(StrainTracker().take(5)) == "Strain tracker: 4 strain, 1 wound"
    assert strain_summary(StrainTracker().take(12)) == "Strain tracker: 9 strain, 2 wounds — Defeat"


@pytest.mark.ui
def test_a_folded_section_keeps_its_state_and_its_title_stays_current():
    async def scenario(app, pilot):
        await start_game(app, pilot)
        section(app, "strain").collapsed = True
        await pilot.pause()
        assert app.query_one("#strain-box-0").region.width == 0
        app.session.strain = app.session.strain.take(4)
        app.update_strain_controls()
        assert section(app, "strain").title == "Strain tracker: 3 strain, 1 wound"
        await click(app, pilot, "#take-strain")
        assert not section(app, "strain").collapsed
        assert app.session.strain.boxes[4]

    run(scenario)
