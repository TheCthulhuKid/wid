import asyncio
from random import Random

import pytest
from helpers import reveal
from test_rollerapp import start_game, text
from test_session_app import click_control, load_game
from textual.widgets import Button, Checkbox, Collapsible, Input, Select

from wid.formatting import strain_summary
from wid.profiles import Genre
from wid.rolls import STRAIN_ENDINGS, PowerMode, RollRequest, StrainTracker
from wid.sessions import SavedSession
from wid.ui.app import RollerApp
from wid.ui.widgets import StrainBox


@pytest.mark.parametrize("points", range(15))
def test_sequential_strain_and_saturation(points):
    tracker = StrainTracker().take(points)
    assert tracker.boxes == (True,) * min(points, 12) + (False,) * max(12 - points, 0)
    assert tracker.defeated == (points >= 12)


def test_recovery_and_manual_corrections():
    tracker = StrainTracker().take(6).set_name(0, "Broken ribs")
    tracker = tracker.set_box(5, False).set_box(4, False)
    assert tracker.take(1).boxes == (True,) * 5 + (False,) * 7
    assert tracker.names[0] == "Broken ribs"
    with pytest.raises(ValueError, match="stay marked"):
        tracker.set_box(0, False)
    released = tracker.set_box(3, False).set_box(0, False)
    assert released.take(1).boxes[0]
    assert StrainTracker().take(11).set_box(11, True).defeated
    assert not StrainTracker().take(12).set_box(11, False).defeated


@pytest.mark.parametrize("wound", STRAIN_ENDINGS)
def test_wound_needs_all_earlier_boxes_marked(wound):
    full = StrainTracker().take(wound)
    assert full.markable(wound)
    assert full.set_box(wound, True).boxes[wound]
    gap = full.set_box(wound - 1, False)
    assert not gap.markable(wound)
    with pytest.raises(ValueError, match="Mark all strain"):
        gap.set_box(wound, True)


def test_wound_cannot_be_marked_on_an_empty_tracker():
    for wound in STRAIN_ENDINGS:
        assert not StrainTracker().markable(wound)
        with pytest.raises(ValueError, match="Mark all strain"):
            StrainTracker().set_box(wound, True)


def test_ordinary_strain_can_be_marked_in_any_order():
    tracker = StrainTracker().set_box(2, True).set_box(0, True)
    assert tracker.boxes[:4] == (True, False, True, False)
    assert tracker.markable(1)
    assert tracker.set_box(1, True).markable(3)


@pytest.mark.parametrize(
    ("points", "locked", "unlockable"),
    [(3, set(), None), (4, {0, 1, 2}, 3), (8, set(range(7)), 7), (12, set(range(11)), 11)],
)
def test_marked_wound_locks_everything_before_it(points, locked, unlockable):
    tracker = StrainTracker().take(points)
    assert tracker.locked_boxes == locked
    for index in locked:
        with pytest.raises(ValueError, match="stay marked"):
            tracker.set_box(index, False)
    if unlockable is not None:
        assert not tracker.set_box(unlockable, False).boxes[unlockable]


def test_wounds_are_unmarked_latest_first():
    tracker = StrainTracker().take(12)
    for latest, earlier in ((11, 7), (7, 3)):
        with pytest.raises(ValueError, match="stay marked"):
            tracker.set_box(earlier, False)
        tracker = tracker.set_box(latest, False)
    assert tracker.locked_boxes == frozenset(range(3))
    assert not tracker.set_box(3, False).locked_boxes


def test_unchanged_boxes_are_never_an_error():
    tracker = StrainTracker().take(8)
    assert tracker.set_box(0, True) == tracker
    assert StrainTracker().set_box(0, False) == StrainTracker()


def test_take_passes_through_a_marked_wound():
    assert StrainTracker().take(5).boxes == (True,) * 5 + (False,) * 7


@pytest.mark.parametrize("points,ending", [(1, 3), (5, 7)])
def test_take_wound_fills_everything_up_to_the_next_wound(points, ending):
    result = StrainTracker().take(points).take_wound()
    assert result.boxes == (True,) * (ending + 1) + (False,) * (11 - ending)


def test_take_wound_after_defeat_is_refused():
    with pytest.raises(ValueError, match="Defeat is already marked"):
        StrainTracker().take(12).take_wound()


@pytest.mark.parametrize("wound", STRAIN_ENDINGS)
def test_tracker_with_a_wound_and_a_gap_is_rejected(wound):
    boxes = [True] * wound + [False] * (12 - wound)
    boxes[wound - 1] = False
    boxes[wound] = True
    with pytest.raises(ValueError, match="needs every earlier box marked"):
        StrainTracker(boxes=boxes)


@pytest.mark.parametrize("points", [-1, True, 1.5, "2"])
def test_invalid_strain_cost(points):
    with pytest.raises(ValueError):
        StrainTracker().take(points)


@pytest.mark.parametrize("index", [-1, 12, True, "0"])
def test_invalid_strain_box(index):
    with pytest.raises(ValueError):
        StrainTracker().set_box(index, True)


@pytest.mark.parametrize("row", [-1, 3, True, "0"])
def test_invalid_wound_row(row):
    with pytest.raises(ValueError):
        StrainTracker().set_name(row, "Scar")


@pytest.mark.parametrize(
    "data",
    [
        {"boxes": []},
        {"boxes": [False] * 13},
        {"boxes": [1] * 12},
        {"names": ["only one"]},
        {"names": ["", "", None]},
    ],
)
def test_invalid_tracker_state(data):
    with pytest.raises(ValueError):
        StrainTracker.model_validate(data)


def test_power_costs_cross_wound_boundary_atomically(session_factory):
    session = session_factory(Genre.HECKBOY)
    session.strain = StrainTracker().take(3)
    request = RollRequest(profile_id=Genre.HECKBOY, attribute="Aberrance", power=PowerMode.ERRATIC)
    session.roll(request, rng=Random(1))
    assert session.strain == StrainTracker().take(5)
    assert session.total_strain == 2
    before = session.model_dump()

    class FailedRandom:
        def randint(self, low, high):
            raise ValueError("failed dice source")

    with pytest.raises(ValueError, match="failed dice"):
        session.roll(request, rng=FailedRandom())
    assert session.model_dump() == before
    session.strain = session.strain.take(12)
    session.roll(request, rng=Random(2))
    assert session.strain.defeated
    assert all(session.strain.boxes)


@pytest.mark.parametrize("genre", list(Genre))
def test_tracker_round_trip_and_recovery(tmp_path, saved_session_factory, genre):
    saved = saved_session_factory(genre)
    saved.session.strain = (
        StrainTracker()
        .take(12)
        .set_name(0, "Ribs 🎲")
        .set_name(1, "[b]Scar[/b]")
        .set_name(2, "Last stand")
    )
    path = tmp_path / "strain.json"
    saved.save(path)
    restored = SavedSession.load(path)
    assert restored.model_dump() == saved.model_dump()
    restored.session.strain = restored.session.strain.set_box(11, False)
    restored.save(path, overwrite=True)
    assert not SavedSession.load(path).session.strain.defeated


@pytest.mark.parametrize("tracker", [{"boxes": []}, {"names": ["", "", None]}])
def test_invalid_saved_tracker_is_rejected(saved_session_factory, tracker):
    data = saved_session_factory().model_dump(mode="json")
    data["session"]["strain"] = tracker
    with pytest.raises(ValueError):
        SavedSession.model_validate(data)


def strain_title(app):
    return app.query_one("#strain-section", Collapsible).title


def test_take_wound_button_fills_the_row():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 45)) as pilot:
            await start_game(app, pilot)
            await click_control(app, pilot, "#take-wound")
            assert app.session.strain.boxes == (True,) * 4 + (False,) * 8
            assert strain_title(app) == "Strain tracker: 3 strain, 1 wound"

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_tracker_mouse_clicks(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await start_game(app, pilot)
            assert strain_title(app) == "Strain tracker: 0 strain, 0 wounds"
            box = app.query_one("#strain-box-0", Checkbox)
            unchecked_background = box.styles.background
            await click_control(app, pilot, "#take-strain")
            assert app.session.strain.boxes[0]
            assert box.value
            assert strain_title(app) == "Strain tracker: 1 strain, 0 wounds"
            assert box.styles.background != unchecked_background
            # Box 0 is unmarked and marked again, then every box in order up to Defeat.
            for index in [0, *range(12)]:
                box = await reveal(app, pilot, f"#strain-box-{index}")
                previous = box.value
                assert await pilot.click(box, offset=(1, 1))
                await pilot.pause()
                assert box.value is not previous
                assert app.session.strain.boxes[index] == box.value
                assert strain_title(app) == strain_summary(app.session.strain)
            assert all(app.session.strain.boxes)

    asyncio.run(scenario())


def test_tracker_ui_keyboard_save_load_and_defeat(tmp_path):
    path = tmp_path / "character.json"

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await start_game(app, pilot)
            assert app.tested_attribute == "Athleticism"
            await click_control(app, pilot, "#take-strain")
            assert app.session.strain.boxes[0]
            box = await reveal(app, pilot, "#strain-box-0")
            box.focus()
            await pilot.press("space")
            assert not app.session.strain.boxes[0]
            app.session.strain = app.session.strain.take(12)
            app.update_strain_controls()
            for row, name in enumerate(("Ribs", "Scar", "Last stand")):
                field = app.query_one(f"#strain-name-{row}", Input)
                field.value = name
            await pilot.pause()
            field = await reveal(app, pilot, "#strain-name-0")
            assert app.query_one("#configuration").content_region.contains_region(field.region)
            field.focus()
            await pilot.press("end", "!")
            assert app.session.strain.names[0] == "Ribs!"
            assert app.session.strain.names == ("Ribs!", "Scar", "Last stand")
            assert "Defeat — character ended. Last stand" in text(app, "#strain-status")
            assert not app.query_one("#roll-attribute-0", Button).disabled
            await pilot.press("ctrl+r")
            assert app.session.current_result is not None
            app.query_one("#session-name", Input).value = "Character"
            app.query_one("#session-path", Input).value = str(path)
            await click_control(app, pilot, "#save-session")
            expected = app.session.strain
            assert SavedSession.load(path).session.strain == expected

        restored = RollerApp()
        async with restored.run_test(size=(80, 24)) as pilot:
            restored.query_one("#session-path", Input).value = str(path)
            await load_game(restored, pilot)
            assert restored.session.strain == expected
            assert strain_title(restored) == strain_summary(expected)
            for index, checked in enumerate(expected.boxes):
                assert restored.query_one(f"#strain-box-{index}", Checkbox).value == checked
            assert restored.query_one("#strain-name-2", Input).value == "Last stand"
            restored.query_one("#strain-box-11", Checkbox).value = False
            await pilot.pause()
            assert not restored.session.strain.defeated
            assert "character ended" not in text(restored, "#strain-status")

    asyncio.run(scenario())


def test_load_confirms_unsaved_tracker_before_start(tmp_path, saved_session_factory):
    path = tmp_path / "character.json"
    saved_session_factory().save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#strain-name-0", Input).value = "Unsaved wound"
            await pilot.pause()
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            await pilot.click("#cancel-session")
            await pilot.pause()
            assert app.session.strain.names[0] == "Unsaved wound"
            assert app.session.attributes is None
            await load_game(app, pilot)
            await pilot.click("#confirm-session")
            await pilot.pause()
            assert app.session.strain == StrainTracker()
            assert app.query_one("#strain-name-0", Input).value == ""

    asyncio.run(scenario())


def test_power_ui_and_confirmed_tracker_reset():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await start_game(app, pilot)
            app.set_power(PowerMode.ERRATIC)
            await pilot.pause()
            await pilot.press("ctrl+r")
            assert app.session.strain == StrainTracker().take(2)
            assert strain_title(app) == "Strain tracker: 2 strain, 0 wounds"
            assert app.query_one("#strain-box-1", Checkbox).value
            app.show_result(app.session.current_result)
            assert app.session.strain == StrainTracker().take(2)
            app.set_power(PowerMode.ERRATIC)
            await pilot.pause()
            await pilot.press("ctrl+r")
            assert app.session.strain == StrainTracker().take(4)
            app.query_one("#strain-name-0", Input).value = "Burned"
            await pilot.pause()
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#cancel-reset")
            await pilot.pause()
            assert app.session.strain.names[0] == "Burned"
            app.query_one("#genre", Select).value = Genre.CORE
            await pilot.pause()
            await pilot.click("#confirm-reset")
            await pilot.pause()
            assert app.session.strain == StrainTracker()
            assert not app.query_one("#strain-box-3", Checkbox).value
            assert app.query_one("#strain-name-0", Input).value == ""

    asyncio.run(scenario())


def box_states(app):
    return {box.index: box.disabled for box in app.query(StrainBox)}


def test_wound_boxes_wait_for_the_strain_before_them():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            assert [i for i, off in box_states(app).items() if off] == [3, 7, 11]
            wound = app.query_one("#strain-box-3", StrainBox)
            assert "Mark all the strain" in str(wound.tooltip)
            for _ in range(3):
                await click_control(app, pilot, "#take-strain")
            assert not wound.disabled
            assert wound.tooltip == wound.description

    asyncio.run(scenario())


def test_marked_wound_locks_the_boxes_before_it_until_cleared():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            for _ in range(4):
                await click_control(app, pilot, "#take-strain")
            states = box_states(app)
            assert [i for i, off in states.items() if off] == [0, 1, 2, 7, 11]
            locked = app.query_one("#strain-box-1", StrainBox)
            assert "stay marked" in str(locked.tooltip)
            assert "strain-box-1" not in [w.id for w in app.screen.focus_chain]
            await pilot.click(locked, offset=(1, 1))
            await pilot.pause()
            assert app.session.strain.boxes[1]
            app.query_one("#strain-box-3", StrainBox).value = False
            await pilot.pause()
            assert not any(box_states(app)[i] for i in (0, 1, 2, 3))
            assert "strain-box-1" in [w.id for w in app.screen.focus_chain]

    asyncio.run(scenario())


def test_refused_change_is_reported_and_undone():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await start_game(app, pilot)
            app.query_one("#strain-box-3", StrainBox).value = True
            await pilot.pause()
            assert not app.session.strain.boxes[3]
            assert not app.query_one("#strain-box-3", StrainBox).value
            assert "Mark all strain" in text(app, "#feedback")
            app.session.strain = app.session.strain.take(4)
            app.update_strain_controls()
            app.query_one("#strain-box-0", StrainBox).value = False
            await pilot.pause()
            assert app.session.strain.boxes[0]
            assert app.query_one("#strain-box-0", StrainBox).value
            assert "stay marked" in text(app, "#feedback")

    asyncio.run(scenario())


def test_locks_are_restored_by_a_load_and_cleared_by_a_kit_change(tmp_path, saved_session_factory):
    path = tmp_path / "locked.json"
    saved = saved_session_factory()
    saved.session.strain = StrainTracker().take(12)
    saved.save(path)

    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one("#session-path", Input).value = str(path)
            await load_game(app, pilot)
            assert [i for i, off in box_states(app).items() if off] == list(range(11))
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await pilot.click("#confirm-reset")
            await pilot.pause()
            assert app.session.strain == StrainTracker()
            assert [i for i, off in box_states(app).items() if off] == [3, 7, 11]

    asyncio.run(scenario())
