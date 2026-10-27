from wid.export import history_markdown
from wid.formatting import sheet_lines
from wid.history import HistoryEntry
from wid.sessions import CharacterDetails

NO_CHARACTER = CharacterDetails()


def roll_entry(saved_session_factory, action="Roll"):
    return HistoryEntry(action=action, result=saved_session_factory().session.current_result)


def test_entries_are_numbered_sections_with_their_text_in_code_blocks(saved_session_factory):
    first = roll_entry(saved_session_factory)
    second = roll_entry(saved_session_factory, "Reroll dice 1, 3")
    note = HistoryEntry(notice="Switched to Heckboy; active test cleared.")

    sheet = sheet_lines(saved_session_factory().session)
    text = history_markdown(
        "Friday", NO_CHARACTER, [first, second, note], sheet=sheet, notes="**Keep** the map.\n"
    )

    assert text.startswith(
        "# Friday\n\n## Sheet\n\n- Ranks: Athleticism 1, Composure 2, Reasoning 3\n"
        "- Strain: 3 strain, 1 wound (Broken arm)\n\n## Notes\n\n**Keep** the map.\n\n"
        "## 1. Roll\n\n```text\n"
    )
    assert "## 2. Reroll dice 1, 3" in text
    assert "## 3. Note\n\n```text\nSwitched to Heckboy; active test cleared.\n```" in text
    assert str(first) in text and str(second) in text
    assert text.endswith("```\n")


def test_player_text_cannot_break_out_of_the_code_block():
    nasty = HistoryEntry(notice="```\n# Heading\n``` and more")

    text = history_markdown("Friday", NO_CHARACTER, [nasty])

    fence = "````"
    assert f"{fence}text\n```\n# Heading\n``` and more\n{fence}\n" in text


def test_the_title_and_character_line_stay_on_their_lines():
    character = CharacterDetails(name="[b]Ada[/b]\n## Not a heading", nature="Brave")

    text = history_markdown("  # Two\nlines ", character, [HistoryEntry(notice="First roll")])

    assert text.splitlines()[:4] == [
        "# # Two lines",
        "",
        "Character: [b]Ada[/b] ## Not a heading, Brave",
        "",
    ]
