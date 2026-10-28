from wid.formatting import strain_summary
from wid.rolls import StrainTracker


def test_summary_text():
    assert strain_summary(StrainTracker()) == "Strain tracker: 0 strain, 0 wounds"
    assert strain_summary(StrainTracker().take(5)) == "Strain tracker: 4 strain, 1 wound"
    assert strain_summary(StrainTracker().take(12)) == "Strain tracker: 9 strain, 2 wounds — Defeat"
