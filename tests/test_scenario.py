import pytest

from wid.dangers import DangerClass, Difficulty
from wid.profiles import Genre
from wid.scenario import Scenario, ScenarioDanger, ScenarioList

LANTERN = ScenarioDanger(
    name="The Lantern Man", danger_class=DangerClass.BRUTE, difficulty=Difficulty.HEAVY
)
CHOIR = ScenarioDanger(
    name="Moth Choir", danger_class=DangerClass.SWARM, difficulty=Difficulty.BOSS, notes="Hums."
)


def test_a_scenario_holds_the_sheet_and_numbers_its_dangers():
    scenario = (
        Scenario()
        .with_text("title", "Night Ferry")
        .with_entry(ScenarioList.WAYPOINTS, 3, "The old bus depot")
        .with_incitement(2, "A new Danger arrives")
        .with_danger(LANTERN, Genre.CORE)
        .with_danger(CHOIR, Genre.CORE)
    )
    assert (scenario.title, scenario.waypoints[3], scenario.incitement[2]) == (
        "Night Ferry",
        "The old bus depot",
        "A new Danger arrives",
    )
    assert [danger.id for danger in scenario.dangers] == [0, 1]

    changed = scenario.changed_danger(1, DangerClass.NIGHTMARE, Difficulty.MEGA, None, Genre.CORE)
    choir = changed.dangers[1]
    assert (choir.id, choir.danger_class, choir.notes) == (1, DangerClass.NIGHTMARE, "Hums.")
    assert changed.with_danger_text(1, "description", "Wings").dangers[1].description == "Wings"
    assert [danger.id for danger in changed.without(0).dangers] == [1]
    with pytest.raises(ValueError, match="No such entry"):
        scenario.with_entry(ScenarioList.NPCS, 6, "Nobody")


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
