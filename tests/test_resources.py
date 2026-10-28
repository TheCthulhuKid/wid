import asyncio
from random import Random

import pytest
from helpers import ScriptedRandom, change_genre, click, start_game, text
from pydantic import ValidationError

from wid.formatting import resources_reminder, spend_summary
from wid.profiles import Genre
from wid.rolls import BonusKind, ResourceEffect, ResourceSpend, RollRequest, StrainTracker
from wid.sessions import SavedSession
from wid.ui.app import RollerApp

KIT = Genre.THIS_ISNT_HAPPENING


@pytest.fixture
def full_pool(session_factory):
    """A This Isn't Happening session with Charity 3 and a full pool of 6."""
    session = session_factory(KIT)
    session.adjust_resources(3)
    return session


def roll(session, **options):
    request = RollRequest(profile_id=KIT, attribute="Instincts", **options)
    return session.roll(request, rng=Random(0))


def test_pool_starts_at_charity_and_stays_between_one_and_six(session_factory):
    session = session_factory(KIT, (3, 2, 1))
    assert session.resources == 1
    with pytest.raises(ValueError, match="cannot go below 1"):
        session.adjust_resources(-1)
    assert session.adjust_resources(5) == 6
    with pytest.raises(ValueError, match="cannot go above 6"):
        session.adjust_resources(1)
    with pytest.raises(ValueError, match="Core WiD has no Resources"):
        session_factory().adjust_resources(1)


def test_spending_needs_a_full_pool_and_resets_to_charity(session_factory, full_pool):
    with pytest.raises(ValueError, match="full pool"):
        session_factory(KIT).spend_resources(ResourceEffect.AUTO_PASS, rng=Random(0))
    spend = full_pool.spend_resources(ResourceEffect.AUTO_PASS, rng=Random(0))
    assert spend == ResourceSpend(effect=ResourceEffect.AUTO_PASS)
    assert full_pool.resources == 3


def test_resources_die_lasts_one_test(full_pool):
    full_pool.spend_resources(ResourceEffect.EXTRA_DIE, rng=Random(0))
    assert len(roll(full_pool, resource_die=True).dice) == 5
    assert not full_pool.resource_die
    with pytest.raises(ValueError, match="No Resources die is waiting"):
        roll(full_pool, resource_die=True)
    with pytest.raises(ValidationError, match="Core WiD has no Resources"):
        RollRequest(resource_die=True)


def test_crafted_item_unlocks_the_third_item_once(full_pool):
    full_pool.set_bonus_name(BonusKind.CRAFTED_ITEM, "Spear")
    roll(full_pool)
    with pytest.raises(ValueError, match="craft an item first"):
        full_pool.apply_item(BonusKind.CRAFTED_ITEM, 0)
    full_pool.spend_resources(ResourceEffect.CRAFT_ITEM, rng=Random(0))
    assert full_pool.apply_item(BonusKind.CRAFTED_ITEM, 0).dice[0].bonus == 1
    full_pool.adjust_resources(3)
    with pytest.raises(ValueError, match="most items"):
        full_pool.spend_resources(ResourceEffect.CRAFT_ITEM, rng=Random(0))
    assert full_pool.resources == 6
    full_pool.lose_crafted_item()
    assert not full_pool.item_crafted
    assert full_pool.bonuses.crafted_item == ""
    full_pool.spend_resources(ResourceEffect.CRAFT_ITEM, rng=Random(0))
    assert full_pool.item_crafted


def test_recovering_strain_clears_the_newest_strain_but_not_wounds(full_pool):
    full_pool.strain = StrainTracker().take_wound().take(2)
    spend = full_pool.spend_resources(ResourceEffect.RECOVER_STRAIN, rng=ScriptedRandom([6]))
    assert (spend.die, spend.recovered) == (6, 2)
    assert full_pool.strain.boxes[:4] == (True,) * 4
    assert not any(full_pool.strain.boxes[4:])
    assert spend_summary(spend, 3) == (
        "Spent 6 Resources: recover 1d6 strain (rolled 6, cleared 2 strain). Resources reset to 3."
    )


def test_reminder_only_for_this_kit_with_extra_hits(full_pool, session_factory):
    many_hits = full_pool.roll(
        RollRequest(profile_id=KIT, attribute="Instincts"), rng=ScriptedRandom([6, 6, 1, 1])
    )
    assert resources_reminder(many_hits) == "Extra hits can be spent to gain Resources."
    one_hit = full_pool.roll(
        RollRequest(profile_id=KIT, attribute="Instincts"), rng=ScriptedRandom([6, 1, 1, 1])
    )
    assert resources_reminder(one_hit) == ""
    core = session_factory()
    assert resources_reminder(core.roll(RollRequest(), rng=ScriptedRandom([6] * 4))) == ""


def test_pool_belongs_to_this_kit(saved_session_factory):
    data = saved_session_factory().model_dump()
    data["session"]["resources"] = 3
    with pytest.raises(ValueError, match="Only This Isn't Happening can have Resources"):
        SavedSession.model_validate(data)


@pytest.mark.ui
def test_resource_controls_spend_and_roll_one_die():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4]))

        async with app.run_test(size=(120, 50)) as pilot:
            await change_genre(app, pilot, KIT)
            await start_game(app, pilot, (1, 2, 3))
            assert text(app, "#resource-count") == "3 / 6"
            assert app.query_one("#spend-resources").disabled
            assert app.query_one("#name-crafted_item").disabled
            for _ in range(3):
                await click(app, pilot, "#resources-up")
            assert text(app, "#resource-count") == "6 / 6"
            assert app.query_one("#resources-up").disabled
            await click(app, pilot, "#spend-resources")
            assert app.screen.query_one("#spend-dialog").size.width < app.size.width
            await pilot.click("#spend-craft_item")
            await pilot.pause()
            assert text(app, "#resource-count") == "3 / 6"
            assert not app.query_one("#name-crafted_item").disabled
            assert str(app.history[-1]).startswith("Spent 6 Resources: craft an item")
            await click(app, pilot, "#roll-d6")
            assert str(app.history[-1]) == "Rolled 1d6: 4."
            await change_genre(app, pilot, Genre.CORE)
            assert not app.query_one("#resource-field").display
            assert not app.query_one("#crafted-row").display

    asyncio.run(scenario())
