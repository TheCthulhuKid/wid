from fastapi.testclient import TestClient
from test_rolls import ScriptedRandom
from textual.color import Color

from wid.game import Game
from wid.profiles import PROFILES, Genre
from wid.ui.outcomes import MIN_CONTRAST, contrast_ratio
from wid.web.app import create_app
from wid.web.view import COLOURS

PAGE = {"HX-Request": "true"}

# A control only one kit has, as it appears in the sheet, and the profile flag that shows it.
KIT_CONTROLS = {
    'name="power-name-0"': "has_powers",
    'formaction="/actions/new-scenario"': "has_tech",
    'name="corruption-amount"': "has_rerolls",
    'formaction="/actions/standing"': "has_standing",
    'formaction="/actions/spend-resources"': "has_resources",
}


def browser(game):
    client = TestClient(create_app(game, "token"), base_url="http://127.0.0.1")
    client.get("/?token=token")
    return client


def act(client, action, **fields):
    return client.post(f"/actions/{action}", data=fields, headers=PAGE)


def test_each_kit_shows_only_its_own_controls():
    client = browser(Game())
    for genre, profile in PROFILES.items():
        sheet = act(client, "change-kit", genre=genre).text
        for control, flag in KIT_CONTROLS.items():
            assert (control in sheet) == getattr(profile, flag), (genre, control)


def test_an_item_and_a_kit_change_through_the_routes():
    game = Game(rng=ScriptedRandom([3, 2, 1, 6]))
    client = browser(game)
    act(client, "start-game", rank=["1", "2", "3"])
    act(client, "roll")
    sheet = act(
        client,
        "apply-bonus",
        sheet="1",
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
    # The question counts what was typed since the sheet was drawn (review issue 2).
    asked = act(client, "new-character", sheet="1", **{"character-name": "Bo"}).text
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
    sheet = act(
        client, "update", sheet="1", notes="# Plan <b>x</b>", **{"notes-preview": "on"}
    ).text
    assert "<h1>Plan &lt;b&gt;x&lt;/b&gt;</h1>" in sheet


def test_bad_fields_are_refused_without_breaking_the_page_or_losing_typing():
    # Review issues 4 and 6.
    game = Game()
    client = browser(game)
    refused = act(client, "update", sheet="1", fear="7", notes="Keep this")
    assert refused.status_code == 200
    assert "Scared" in refused.text
    assert game.fear_level == 0
    assert game.notes == "Keep this"
    assert client.get("/").status_code == 200
