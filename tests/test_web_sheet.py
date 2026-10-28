from helpers import ScriptedRandom, act, browser
from textual.color import Color

from wid.game import Game
from wid.gm import GmGame
from wid.profiles import PROFILES, Genre
from wid.ui.outcomes import MIN_CONTRAST, contrast_ratio
from wid.web.view import COLOURS

# A control only one kit has, as it appears in the sheet, and the profile flag that shows it.
KIT_CONTROLS = {
    'name="power-name-0"': "has_powers",
    'formaction="/actions/new-scenario"': "has_tech",
    'name="corruption-amount"': "has_rerolls",
    'formaction="/actions/standing"': "has_standing",
    'formaction="/actions/spend-resources"': "has_resources",
}


def test_each_kit_shows_only_its_own_controls():
    client = browser(Game())
    for genre, profile in PROFILES.items():
        sheet = act(client, "change-kit", genre=genre).text
        for control, flag in KIT_CONTROLS.items():
            assert (control in sheet) == getattr(profile, flag), (genre, control)


def test_an_item_and_a_kit_change_through_the_routes(tmp_path):
    game = Game(rng=ScriptedRandom([3, 2, 1, 6, 4, 4, 4, 4]))
    client = browser(game)
    act(client, "start-game", rank=["1", "2", "3"])
    act(client, "roll")
    sheet = act(
        client,
        "apply-bonus",
        kind="appropriate_item",
        die="1",
        **{"name-appropriate_item": "Sword"},
    ).text
    assert game.session.current_result.dice[1].bonus == 1
    assert "Appropriate Item Sword: +1 to die 2" in sheet
    assert "A genre kit lasts the whole game" in act(client, "change-kit", genre="oldheart").text
    act(client, "change-kit", **{"confirm-genre": "oldheart"})
    assert game.session.profile_id == Genre.OLDHEART
    assert game.history == []
    # Save first saves, then changes kit with nothing left to lose.
    act(client, "start-game", rank=["1", "2", "3"])
    act(client, "roll")
    fields = {"session-name": "Friday", "session-path": str(tmp_path / "game.json")}
    asked = act(client, "change-kit", genre="core", **fields).text
    assert 'name="save-first" value="core"' in asked
    sheet = act(client, "change-kit", **{"save-first": "core"}, **fields).text
    assert "Saved Friday to" in sheet and "New Core WiD game started." in sheet
    assert (tmp_path / "game.json").is_file()
    # The question counts what was typed since the sheet was drawn.
    asked = act(client, "new-character", **{"character-name": "Bo"}).text
    assert "Start a new character?" in asked


def test_outcome_and_button_colours_stay_readable_in_light_and_dark():
    for scheme, colours in COLOURS.items():
        paper = Color.parse(colours["paper"])
        for outcome in ("hit", "miss", "fumble"):
            ratio = contrast_ratio(Color.parse(colours[outcome]), paper)
            assert ratio >= MIN_CONTRAST, (scheme, outcome)
        button = contrast_ratio(Color.parse(colours["on-danger"]), Color.parse(colours["danger"]))
        assert button >= 4.5, scheme


def test_the_notes_preview_renders_markdown_without_raw_html():
    client = browser(Game())
    notes = "# Plan <b>x</b>\n\n[Map](https://example.com)"
    sheet = act(client, "update", notes=notes, **{"notes-preview": "on"}).text
    assert "<h1>Plan &lt;b&gt;x&lt;/b&gt;</h1>" in sheet
    assert 'href="https://example.com" target="_blank"' in sheet


def test_bad_fields_are_refused_without_breaking_the_page_or_losing_typing():
    game = Game()
    client = browser(game)
    refused = act(client, "update", fear="7", notes="Keep this")
    assert refused.status_code == 200
    assert "Scared" in refused.text
    assert game.fear_level == 0
    assert game.notes == "Keep this"
    assert client.get("/").status_code == 200
    game.start_game((1, 2, 3))
    game.roll()
    act(client, "update", die="9")
    assert game.item_target is None


def test_the_gm_page_runs_a_scene_and_refuses_a_player_save():
    game = GmGame(rng=ScriptedRandom([4, 2, 5]))
    client = browser(game)
    page = client.get("/").text
    assert "Activate Danger" in page and "Start game" not in page
    act(client, "change-kit", genre="heckboy")
    sheet = act(
        client,
        "add-danger",
        **{"new-danger-name": "Zeus", "danger-class": "titan", "difficulty": "mega"},
    ).text
    assert "Zeus: Mega Titan — threshold 16, 2 hits to pass" in sheet
    assert "<td>Dominate</td>" in sheet
    sheet = act(client, "activate", **{"danger-name-0": "Jupiter"}).text
    assert "Dominate — PC who acted most recently, defending with Savvy" in sheet
    assert game.scene.dangers[0].name == "Jupiter"
    asked = act(client, "change-kit", genre="core").text
    assert 'name="keep-scene"' in asked and 'name="save-first"' in asked
    sheet = act(client, "change-kit", **{"keep-scene": "core"}).text
    assert "Kit changed to Core WiD. Dropped Jupiter." in sheet
    assert game.genre == Genre.CORE
    player_save = Game()
    player_save.start_game((1, 2, 3))
    refused = act(client, "upload", **{"session-file": player_save.save_text()}).text
    assert "start wid without --gm" in refused
