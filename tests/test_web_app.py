from fastapi.testclient import TestClient
from test_rolls import ScriptedRandom

from wid.game import Game
from wid.web.app import TOKEN_COOKIE, create_app

TOKEN = "launch-token"
PAGE = {"HX-Request": "true"}


def client(game=None, host="127.0.0.1"):
    app = create_app(game or Game(rng=ScriptedRandom([4] * 8)), TOKEN)
    return TestClient(app, base_url=f"http://{host}")


def signed_in(game):
    """A browser that opened the address ``wid --web`` printed, so it holds the cookie."""
    browser = client(game)
    browser.get(f"/?token={TOKEN}")
    return browser


def test_actions_take_the_sheet_fields_change_the_game_and_return_the_sheet():
    game = Game(rng=ScriptedRandom([4] * 4))
    browser = signed_in(game)
    refused = browser.post("/actions/roll", headers=PAGE)
    assert "Set attributes" in refused.text
    browser.post("/actions/start-game", data={"rank": ["1", "2", "3"]}, headers=PAGE)
    sheet = {"sheet": "1", "fear": "0", "name-appropriate_item": "Sword <b>"}
    response = browser.post("/actions/roll", data=sheet, headers=PAGE)
    assert response.status_code == 200
    assert game.session.bonuses.appropriate_item == "Sword <b>"
    assert "Roll: core, Athleticism rank 1" in response.text
    assert "<b>" not in response.text


def test_the_token_is_swapped_for_a_cookie_and_then_required():
    browser = client()
    assert browser.get("/").status_code == 403
    opened = browser.get(f"/?token={TOKEN}", follow_redirects=False)
    assert (opened.status_code, opened.headers["location"]) == (303, "/")
    assert "samesite=strict" in opened.headers["set-cookie"].lower()
    assert browser.cookies[TOKEN_COOKIE] == TOKEN
    assert browser.get("/").status_code == 200


def test_actions_need_the_page_header_and_a_local_host():
    browser = signed_in(Game())
    assert browser.post("/actions/roll").status_code == 403
    assert client(host="wid.example").get(f"/?token={TOKEN}").status_code == 400
