import asyncio
from random import Random

import pytest
from helpers import ScriptedRandom, change_genre, click, start_game, text
from textual.widgets import Input, Select

from wid.formatting import check_summary
from wid.profiles import Genre
from wid.rolls import OLDHEART_MAX_POOL, RollRequest, manifestation_check
from wid.sessions import SavedSession
from wid.ui.app import RollerApp

KIT = Genre.OLDHEART


def test_a_check_manifests_when_the_total_is_at_or_under_the_score():
    assert manifestation_check(2, 5, ScriptedRandom([2, 3])).triggered
    assert not manifestation_check(2, 5, ScriptedRandom([3, 3])).triggered


def test_corruption_is_gained_with_a_check_until_the_character_succumbs(session_factory):
    session = session_factory(KIT)
    check = session.add_corruption(2, rng=ScriptedRandom([1, 1]))
    assert (session.total_corruption, check.score, check.triggered) == (2, 2, True)
    assert len(session.manifestations) == 1
    session.add_manifestation()
    session.add_corruption(1, rng=ScriptedRandom([1]))
    assert session.succumbed
    check = session.add_corruption(1, rng=ScriptedRandom([1]))
    assert len(session.manifestations) == 3
    assert check_summary(check).endswith("no effect: the character has already succumbed")
    with pytest.raises(ValueError, match="Core WiD has no Corruption"):
        session_factory().add_corruption(1, rng=Random(0))


def test_manifestations_change_depravity_and_hospitality_pools():
    def pool(attribute, manifestations, fear=0, assisted=False):
        request = RollRequest(
            profile_id=KIT,
            attribute=attribute,
            manifestations=manifestations,
            fear_level=fear,
            assisted=assisted,
        )
        return request.pool_size

    assert pool("Depravity", 2) == 6
    assert pool("Hospitality", 2) == 2
    assert pool("Fitness", 2) == 4
    assert pool("Hospitality", 3, fear=3) == 1
    assert pool("Depravity", 3, assisted=True) == OLDHEART_MAX_POOL


def test_manifestations_belong_to_oldheart(saved_session_factory):
    data = saved_session_factory().model_dump()
    data["session"]["manifestations"] = ("Scales",)
    with pytest.raises(ValueError, match="Only Oldheart can have manifestations"):
        SavedSession.model_validate(data)


@pytest.mark.ui
def test_gaining_corruption_by_hand_checks_and_shows_manifestations():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 1]))
        async with app.run_test(size=(120, 50)) as pilot:
            assert not app.query_one("#corruption-field").display
            await change_genre(app, pilot, KIT)
            await start_game(app, pilot)
            app.query_one("#corruption-amount", Select).value = 2
            await click(app, pilot, "#gain-corruption")
            assert text(app, "#corruption-status") == "Corruption 2 — 1 of 3 manifestations"
            assert str(app.history[-1]).startswith("Gained 2 Corruption. Manifestation check")
            assert not app.query_one("#manifestation-name-0", Input).disabled
            app.query_one("#manifestation-name-0", Input).value = "Scaly arm"
            await pilot.pause()
            assert app.session.manifestations == ("Scaly arm",)
            app.game.tested_attribute = "Depravity"
            app.update_preview()
            assert "Depravity +1d6, Hospitality -1d6" in text(app, "#pool")
            await click(app, pilot, "#remove-manifestation")
            assert app.session.manifestations == ()
            assert app.query_one("#manifestation-name-0", Input).value == ""

    asyncio.run(scenario())
