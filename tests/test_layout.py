import asyncio

import pytest
from helpers import reveal
from test_rollerapp import start_game, text
from test_rolls import ScriptedRandom
from textual.widgets import Button, Checkbox, Input, Label, RichLog, Select

from wid.profiles import Genre
from wid.rolls import PowerMode
from wid.ui.app import RollerApp


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_compact_left_aligned_attributes_and_named_expertise(size):
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4]))
        async with app.run_test(size=size) as pilot:
            for index in range(3):
                row = app.query_one(f"#attribute-row-{index}")
                label = app.query_one(f"#attribute-label-{index}")
                rank = app.query_one(f"#attribute-rank-{index}")
                button = app.query_one(f"#roll-attribute-{index}")
                assert label.region.x == row.content_region.x
                assert rank.region.x == label.region.right
                assert rank.region.x - label.region.x <= 14
                assert button.region.x == rank.region.right + 1
            await start_game(app, pilot)
            assisted_field = app.query_one("#assisted-field")
            labels = [str(label.render()) for label in assisted_field.query(Label)]
            labels.append(str(app.query_one("#assisted", Checkbox).label))
            assert " ".join(labels).count("Assisted") == 1
            expertise_field = app.query_one("#expertise-field")
            name = app.query_one("#name-expertise", Input)
            checkbox = app.query_one("#expertise", Checkbox)
            apply = app.query_one("#apply-expertise", Button)
            assert name in expertise_field.query(Input)
            name.scroll_visible(animate=False)
            await pilot.pause()
            assert name.region.y == checkbox.region.y == apply.region.y
            assert checkbox.region.right <= name.region.x
            assert name.region.right <= apply.region.x
            assert name.region.width >= 10
            assert expertise_field.content_region.contains_region(apply.region)
            name.focus()
            await pilot.press("h", "e", "a", "l", "i", "n", "g", "tab")
            assert app.session.bonuses.expertise == "healing"
            await pilot.press("ctrl+r")
            assert await pilot.click(apply)
            assert app.session.current_result.totals().expertise_hits == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_start_game_shares_first_row_with_genre(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            genre = app.query_one("#genre", Select)
            button = app.query_one("#start-game", Button)
            assert button.region.y == genre.region.y
            assert button.region.x >= genre.region.right
            assert app.query_one("#configuration").content_region.contains_region(button.region)
            assert await pilot.click(button)
            await pilot.pause()
            assert app.session.attributes is not None
            assert not genre.disabled
            assert not button.display
            app.query_one("#genre", Select).value = Genre.OLDHEART
            await pilot.pause()
            assert button.display
            assert button.region.y == genre.region.y
            assert button.region.x >= genre.region.right

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_short_inputs_share_rows_and_remain_accessible(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            ranks = [app.query_one(f"#attribute-rank-{index}") for index in range(3)]
            assert len({field.region.y for field in ranks}) == 3
            assert ranks[0].region.bottom <= ranks[1].region.y
            await start_game(app, pilot)
            fear = app.query_one("#fear", Select)
            assert fear.size.width <= 10
            fear.scroll_visible(animate=False)
            fear.focus()
            await pilot.press("enter", "down", "enter")
            assert fear.value == 1
            assert fear.region.y == app.query_one("#assisted").region.y
            assert fear.region.y == app.query_one("#expertise").region.y
            name = await reveal(app, pilot, "#name-appropriate_item")
            assert app.query_one("#configuration").content_region.contains_region(name.region)

    asyncio.run(scenario())


def test_maximum_pool_uses_single_line_results_and_item_targets():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([4] * 7))
        async with app.run_test(size=(100, 35)) as pilot:
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            await start_game(app, pilot)
            app.query_one("#assisted").value = True
            app.query_one("#power", Select).value = PowerMode.ERRATIC
            await pilot.pause()
            await pilot.press("ctrl+r")
            app.query_one("#item-target", Select).value = 6
            assert app.query_one("#item-target", Select).value == 6
            dice = app.query_one("#dice")
            assert dice.size.height == 7
            assert "7: 4+0=4 hit" in text(app, "#dice")
            assert "Die 7: raw 4 +0 = 4 — hit" in str(app.history[-1])

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45), (200, 50)])
def test_configuration_gets_two_thirds_of_workspace(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            configuration = app.query_one("#configuration")
            output = app.query_one("#output")
            assert abs(output.region.width - size[0] / 3) <= 1
            assert abs(configuration.region.width - 2 * output.region.width) <= 2
            assert output.region.right == size[0]
            button = app.query_one("#toggle-history", Button)
            assert output.content_region.contains_region(button.region)
            assert await pilot.click(button)

    asyncio.run(scenario())


def test_history_toggle_reclaims_space_and_keeps_hidden_rolls():
    async def scenario():
        app = RollerApp(rng=ScriptedRandom([1, 2, 3, 4] * 3))
        async with app.run_test(size=(80, 24)) as pilot:
            panel = app.query_one("#history-panel")
            toggle = app.query_one("#toggle-history", Button)
            assert not panel.display
            assert str(toggle.label) == "Show log"
            await start_game(app, pilot)
            await pilot.press("ctrl+r")
            height_without_log = app.query_one("RollerGroup").region.height
            assert height_without_log >= 16
            first_result = text(app, "#dice")
            await pilot.click("#toggle-history")
            await pilot.pause()
            assert panel.display
            assert str(toggle.label) == "Hide log"
            assert panel.size.height <= 6
            assert app.query_one("RollerGroup").region.height < height_without_log
            log = app.query_one("#log", RichLog)
            assert log.lines
            lines = len(log.lines)
            log.focus()
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert not panel.display
            assert app.focused is toggle
            assert app.query_one("RollerGroup").region.height == height_without_log
            await pilot.press("ctrl+r", "ctrl+l")
            await pilot.pause()
            assert panel.display
            assert len(log.lines) > lines
            assert len(app.history) == 2
            assert text(app, "#dice") == first_result

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (100, 35), (140, 45)])
def test_wound_names_and_strain_boxes_have_room(size):
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=size) as pilot:
            await start_game(app, pilot)
            configuration = app.query_one("#configuration")
            for row in range(3):
                field = await reveal(app, pilot, f"#strain-name-{row}")
                assert field.size.width >= 24
                assert configuration.content_region.contains_region(field.region)
                field.focus()
                await pilot.press("W", "o", "u", "n", "d")
                assert app.session.strain.names[row] == "Wound"
                for column in range(4):
                    box = app.query_one(f"#strain-box-{row * 4 + column}")
                    assert box.region.x >= configuration.content_region.x
                    assert box.region.right <= configuration.content_region.right
                ending = app.query_one(f"#strain-box-{row * 4 + 3}", Checkbox)
                for checked in (False, True):
                    ending.value = checked
                    await pilot.pause()
                    assert ending.content_size.width >= ending.get_content_width(
                        ending.size, app.size
                    )
            if size[0] >= 100:
                assert app.query_one("#configuration").region.width >= 42

    asyncio.run(scenario())


def test_layout_adapts_on_resize_without_losing_edits():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(140, 45)) as pilot:
            field = await reveal(app, pilot, "#strain-name-0")
            field.value = "Broken ribs"
            await pilot.pause()
            box = await reveal(app, pilot, "#strain-box-3")
            assert field.region.y == box.region.y
            await pilot.resize_terminal(80, 24)
            await pilot.pause()
            assert field.region.y > box.region.y
            assert field.size.width >= 24
            await pilot.resize_terminal(140, 45)
            await pilot.pause()
            assert field.region.y == box.region.y
            assert field.value == "Broken ribs"
            assert app.session.strain.names[0] == "Broken ribs"

    asyncio.run(scenario())


def test_history_shortcut_during_confirmation_preserves_dialog():
    async def scenario():
        app = RollerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            app.session.strain = app.session.strain.take(1)
            app.query_one("#genre", Select).value = Genre.HECKBOY
            await pilot.pause()
            dialog = app.screen
            await pilot.press("ctrl+l")
            assert app.screen is dialog
            await pilot.click("#cancel-reset")
            await pilot.pause()
            assert not app.query_one("#history-panel").display
            assert app.session.profile_id == Genre.CORE
            assert app.session.strain.boxes[0]

    asyncio.run(scenario())
