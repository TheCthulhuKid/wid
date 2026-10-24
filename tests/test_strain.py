import asyncio
from random import Random

import pytest
from test_rollerapp import start_game, text
from test_session_app import click_control, load_game
from textual.widgets import Button, Checkbox, Input, Select

from wid.profiles import Genre
from wid.rolls import PowerMode, RollRequest, StrainTracker
from wid.sessions import SavedSession
from wid.ui.app import RollerApp


@pytest.mark.parametrize("points", range(15))
def test_sequential_strain_and_saturation(points):
    tracker = StrainTracker().take(points)
    assert tracker.boxes == (True,) * min(points, 12) + (False,) * max(12 - points, 0)
    assert tracker.defeated == (points >= 12)


def test_recovery_and_manual_corrections():
    tracker = StrainTracker().take(6).set_name(0, "Broken ribs")
    tracker = tracker.set_box(4, False).set_box(5, False)
    assert tracker.take(1).boxes == (True,) * 5 + (False,) * 7
    assert tracker.names[0] == "Broken ribs"
    tracker = tracker.set_box(0, False)
    assert not tracker.take(1).boxes[0]
    assert tracker.take(1).boxes[4]
    assert not tracker.set_box(3, False).take(1).boxes[3]
    assert StrainTracker().set_box(11, True).defeated
    assert not StrainTracker().take(12).set_box(11, False).defeated


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
        .set_box(4, False)
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


@pytest.mark.parametrize("attribute", ["Tested attribute", "Attribute 2", "Attribute 3"])
def test_legacy_core_labels_migrate(saved_session_factory, attribute):
    data = saved_session_factory().model_dump(mode="json")
    position = ("Tested attribute", "Attribute 2", "Attribute 3").index(attribute)
    for request in (data["draft"], data["session"]["current_result"]["request"]):
        request.update(attribute=attribute, attribute_rank=position + 1)
    data["session"].pop("strain")
    saved = SavedSession.model_validate(data)
    expected = ("Athleticism", "Composure", "Reasoning")[position]
    assert saved.draft.attribute == saved.session.current_result.request.attribute == expected
    assert data["draft"]["attribute"] == attribute
    assert saved.session.strain == StrainTracker()


@pytest.mark.parametrize("total", [0, 3, 4, 8, 12, 30])
def test_legacy_power_strain_migrates(saved_session_factory, total):
    data = saved_session_factory(Genre.HECKBOY).model_dump(mode="json")
    data["session"].pop("strain")
    data["session"].update(total_strain=total, current_result=None)
    assert SavedSession.model_validate(data).session.strain == StrainTracker().take(total)


@pytest.mark.parametrize("tracker", [{"boxes": []}, {"names": ["", "", None]}])
def test_invalid_saved_tracker_is_not_replaced_by_legacy_default(saved_session_factory, tracker):
    data = saved_session_factory().model_dump(mode="json")
    data["session"]["strain"] = tracker
    with pytest.raises(ValueError):
        SavedSession.model_validate(data)


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_tracker_mouse_clicks(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await start_game(app, pilot)
            assert text(app, "#strain-total") == "Character strain: 0 / 12 marked"
            box = app.query_one("#strain-box-0", Checkbox)
            unchecked_background = box.styles.background
            await click_control(app, pilot, "#take-strain")
            assert app.session.strain.boxes[0]
            assert box.value
            assert text(app, "#strain-total") == "Character strain: 1 / 12 marked"
            assert box.styles.background != unchecked_background
            for index in range(12):
                box = app.query_one(f"#strain-box-{index}", Checkbox)
                box.scroll_visible(animate=False)
                await pilot.pause()
                previous = box.value
                assert await pilot.click(box, offset=(1, 1))
                await pilot.pause()
                assert box.value is not previous
                assert app.session.strain.boxes[index] == box.value
                assert text(app, "#strain-total") == (
                    f"Character strain: {sum(app.session.strain.boxes)} / 12 marked"
                )

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
            box = app.query_one("#strain-box-0", Checkbox)
            box.scroll_visible(animate=False)
            box.focus()
            await pilot.press("space")
            assert not app.session.strain.boxes[0]
            for index in (3, 7, 11):
                app.query_one(f"#strain-box-{index}", Checkbox).value = True
            for row, name in enumerate(("Ribs", "Scar", "Last stand")):
                field = app.query_one(f"#strain-name-{row}", Input)
                field.value = name
            await pilot.pause()
            field = app.query_one("#strain-name-0", Input)
            field.scroll_visible(animate=False)
            await pilot.pause()
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
            assert text(restored, "#strain-total") == (
                f"Character strain: {sum(expected.boxes)} / 12 marked"
            )
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
            app.query_one("#power", Select).value = PowerMode.ERRATIC
            await pilot.pause()
            await pilot.press("ctrl+r")
            assert app.session.strain == StrainTracker().take(2)
            assert text(app, "#strain-total") == "Character strain: 2 / 12 marked"
            assert app.query_one("#strain-box-1", Checkbox).value
            app.show_result(app.session.current_result)
            assert app.session.strain == StrainTracker().take(2)
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
