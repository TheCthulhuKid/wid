from wid.export import fence_for, history_markdown
from wid.history import HistoryEntry
from wid.sessions import CharacterDetails

NO_CHARACTER = CharacterDetails()


def roll_entry(saved_session_factory, action="Roll"):
    return HistoryEntry(action=action, result=saved_session_factory().session.current_result)


def test_entries_are_numbered_sections_with_their_text_in_code_blocks(saved_session_factory):
    first = roll_entry(saved_session_factory)
    second = roll_entry(saved_session_factory, "Reroll dice 1, 3")
    note = HistoryEntry(notice="Switched to Heckboy; active test cleared.")

    text = history_markdown("Friday", NO_CHARACTER, [first, second, note])

    assert text.startswith("# Friday\n\n## 1. Roll\n\n```text\n")
    assert "## 2. Reroll dice 1, 3" in text
    assert "## 3. Note\n\n```text\nSwitched to Heckboy; active test cleared.\n```" in text
    assert str(first) in text and str(second) in text
    assert text.endswith("```\n")


def test_character_line_lists_only_the_details_that_are_set():
    character = CharacterDetails(name="Ada", nature="Brave")

    text = history_markdown("Friday", character, [])

    assert "Character: Ada, Brave\n" in text
    assert "Character:" not in history_markdown("Friday", NO_CHARACTER, [])


def test_title_is_one_clean_line_with_a_fallback():
    assert history_markdown("  Two\nlines  here ", NO_CHARACTER, []).startswith(
        "# Two lines here\n"
    )
    assert history_markdown("   ", NO_CHARACTER, []).startswith("# Session history\n")


def test_fence_is_longer_than_any_backtick_run_in_the_text():
    assert fence_for("plain") == "```"
    assert fence_for("a ``` b") == "````"
    assert fence_for("`` and ````` and `") == "``````"


def test_player_text_cannot_break_out_of_the_code_block():
    nasty = HistoryEntry(notice="```\n# Heading\n``` and more")

    text = history_markdown("Friday", NO_CHARACTER, [nasty])

    fence = "````"
    assert f"{fence}text\n```\n# Heading\n``` and more\n{fence}\n" in text


def test_player_markup_in_the_title_and_character_stays_on_their_lines():
    character = CharacterDetails(name="[b]Ada[/b]\n## Not a heading")

    text = history_markdown("# Hash", character, [HistoryEntry(notice="First roll")])

    assert text.splitlines()[:4] == ["# # Hash", "", "Character: [b]Ada[/b] ## Not a heading", ""]
