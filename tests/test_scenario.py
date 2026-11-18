import pytest

from wid.dangers import DangerClass, Difficulty
from wid.profiles import Genre
from wid.scenario import Scenario, ScenarioDanger, ScenarioList, Slot

LANTERN = ScenarioDanger(
    name="The Lantern Man", danger_class=DangerClass.BRUTE, difficulty=Difficulty.HEAVY
)
CHOIR = ScenarioDanger(
    name="Moth Choir", danger_class=DangerClass.SWARM, difficulty=Difficulty.BOSS, notes="Hums."
)


def test_a_scenario_holds_the_sheet_and_numbers_its_dangers():
    scenario = (
        Scenario()
        .with_danger(LANTERN, Genre.CORE)
        .with_danger(CHOIR, Genre.CORE)
        .with_typed(
            {
                (Slot.TEXT, "title"): "Night Ferry",
                (ScenarioList.WAYPOINTS.value, 3): "The old bus depot",
                (Slot.INCITEMENT, 2): "A new Danger arrives",
                (Slot.DANGER, 1, "description"): "Wings",
            }
        )
    )
    assert (scenario.title, scenario.waypoints[3], scenario.incitement[2]) == (
        "Night Ferry",
        "The old bus depot",
        "A new Danger arrives",
    )
    assert [danger.id for danger in scenario.dangers] == [0, 1]
    assert scenario.dangers[1].description == "Wings"

    changed = scenario.changed_danger(1, DangerClass.NIGHTMARE, Difficulty.MEGA, None, Genre.CORE)
    choir = changed.dangers[1]
    assert (choir.id, choir.danger_class, choir.notes) == (1, DangerClass.NIGHTMARE, "Hums.")
    assert [danger.id for danger in changed.without(0).dangers] == [1]


def test_a_scenario_refuses_what_the_kit_lacks():
    titan = ScenarioDanger(
        name="Colossus", danger_class=DangerClass.TITAN, difficulty=Difficulty.MEGA
    )
    with pytest.raises(ValueError, match="has no Titans"):
        Scenario().with_danger(titan, Genre.CORE)
    full = Scenario()
    for _ in range(6):
        full = full.with_danger(LANTERN, Genre.CORE)
    with pytest.raises(ValueError, match="up to 6 Dangers"):
        full.with_danger(LANTERN, Genre.CORE)

    heckboy = Scenario().with_danger(LANTERN, Genre.HECKBOY).with_danger(titan, Genre.HECKBOY)
    core, dropped = heckboy.in_kit(Genre.CORE)
    assert ([danger.name for danger in core.dangers], dropped) == (
        ["The Lantern Man"],
        ["Colossus"],
    )
    assert heckboy.fits(Genre.HECKBOY) and not heckboy.fits(Genre.CORE)
