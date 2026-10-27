from helpers import ScriptedRandom, act, browser

from wid.game import Game


def started(faces=(4,) * 8):
    game = Game(rng=ScriptedRandom(faces))
    game.start_game((1, 2, 3))
    game.roll()
    return game


def test_a_browser_save_opens_in_the_terminal_and_the_reverse(tmp_path):
    path = str(tmp_path / "game.json")
    game = started()
    client = browser(game)
    sheet = act(client, "save", **{"session-name": "Friday", "session-path": path}).text
    assert f"Saved Friday to {path}." in sheet
    terminal = Game()
    terminal.load(*terminal.read_save(path))
    assert terminal.session.model_dump() == game.session.model_dump()

    # A browser with nothing to lose loads a terminal save at once.
    terminal.name = "From the terminal"
    terminal.save(overwrite=True)
    fresh = Game()
    act(browser(fresh), "load", **{"session-path": path})
    assert fresh.name == "From the terminal"


def test_saving_over_a_file_and_loading_over_a_game_ask_first(tmp_path):
    path = str(tmp_path / "game.json")
    game = started()
    client = browser(game)
    fields = {"session-name": "Friday", "session-path": path}
    act(client, "save", **fields)
    asked = act(client, "save", **fields).text
    assert "Replace the existing save at" in asked
    assert 'name="overwrite"' in asked
    assert "Saved Friday" in act(client, "save", overwrite="1", **fields).text

    other = started()
    other_client = browser(other)
    asked = act(other_client, "load", **{"session-path": path}).text
    assert "Load Friday? This replaces the current game and history." in asked
    assert other.name == ""
    act(other_client, "load", confirm="1", **{"session-path": path})
    assert other.name == "Friday"


def test_the_history_exports_to_a_file_and_downloads(tmp_path):
    game = started()
    game.name = "Friday"
    # A non-ASCII letter: the download name must still fit in a header.
    game.path = str(tmp_path / "kämpaign.json")
    client = browser(game)
    target = str(tmp_path / "notes.md")
    assert (
        f"Exported 1 history entries to {target}."
        in act(client, "export", **{"export-path": target}).text
    )
    asked = act(client, "export", **{"export-path": target}).text
    assert "Replace the existing file at" in asked
    # Replace must write the file the question names.
    assert f'name="export-path" value="{target}"' in asked

    download = client.get("/history.md")
    assert download.status_code == 200
    assert download.headers["content-disposition"] == 'attachment; filename="k_mpaign.md"'
    assert download.text == game.history_text()
    assert download.text.startswith("# Friday")
