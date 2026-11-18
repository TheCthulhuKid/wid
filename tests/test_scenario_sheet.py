import pytest

from wid.dangers import DangerClass, Difficulty
from wid.gm import GmGame
from wid.profiles import Genre
from wid.scenario_sheet import ChooseScenario, read_sheets, write_sheet

# A made-up sheet of two scenarios, written as a GM would: a file title, a Tasks section wid
# skips, the old name Competent, and a Danger with no loadout table.
SHEET = """# My sheets

---

# Night Ferry

*By A. Writer*

**Pitch:** The last ferry
never docks.

**Waypoints**
- The car deck
- The bridge

**Tasks**
- **Low:** strain equal number of PCs

**Incitement**
| d6 | |
|----|---|
| 1–2 | The **fog** thickens |

### Colossus
*Competent brute* · **Hits:** 1 · **Threshold:** PCs x 2

| d6 | Ability | Target | Attribute |
|----|---------|--------|-----------|
| 1 | Harass | PC who acted most recently | Athleticism |
| 2 | Scare | PC who acted most recently | Athleticism |
| 3 | Kill | PC who acted most recently | Composure |
| 4 | Kill | PC(s) with highest **scared** | Composure |
| 5 | Kill | PC(s) with most **strain** | Reasoning |
| 6 | Harass | PC(s) with most **wounds** | Reasoning |

Wades through the hold.

**Notes:** Starts below deck.

# Low Tide

### Zeus
*Mega Titan*
"""


def test_a_sheet_reads_writes_and_reads_back_the_same():
    ferry, tide = read_sheets(SHEET)
    assert (ferry.title, ferry.author, ferry.pitch) == (
        "Night Ferry",
        "A. Writer",
        "The last ferry\nnever docks.",
    )
    assert ferry.waypoints[:3] == ("The car deck", "The bridge", "")
    assert ferry.incitement == ("The **fog** thickens", "", "")
    colossus = ferry.dangers[0]
    assert (colossus.difficulty, colossus.danger_class) == (Difficulty.HEAVY, DangerClass.BRUTE)
    assert (colossus.description, colossus.notes) == (
        "Wades through the hold.",
        "Starts below deck.",
    )
    assert tide.dangers[0].danger_class == DangerClass.TITAN
    for scenario in (ferry, tide):
        assert read_sheets(write_sheet(scenario, Genre.HECKBOY)) == (scenario,)


def test_a_danger_of_an_unknown_class_is_refused_by_name():
    with pytest.raises(ValueError, match='Low Tide, Zeus: wid knows no class "Giant"'):
        read_sheets(SHEET.replace("*Mega Titan*", "*Mega Giant*"))


def test_the_gm_game_imports_the_chosen_scenario():
    game = GmGame()
    game.add_scenario_danger("Old", DangerClass.SWARM, Difficulty.PETTY)
    with pytest.raises(ChooseScenario) as asked:
        game.import_scenario(SHEET)
    assert asked.value.titles == ("Night Ferry", "Low Tide")
    with pytest.raises(ValueError, match="Low Tide, Zeus: Core WiD has no Titans."):
        game.import_scenario(SHEET, 1)
    assert game.import_scenario(SHEET, 0) == "Imported the scenario Night Ferry."
    # Numbered on from the scenario it replaces, so the old id 0 is never reused.
    assert [danger.id for danger in game.scenario.dangers] == [1]
    game.undo()
    assert game.scenario.dangers[0].name == "Old"
