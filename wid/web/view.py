"""What the browser sheet shows: its colours, the notes preview and the template context."""

from markdown_it import MarkdownIt

from wid.formatting import (
    BONUS_LABELS,
    corruption_status,
    pool_line,
    resources_line,
    resources_reminder,
    strain_status,
    strain_summary,
    tech_starting_line,
)
from wid.game import Game
from wid.profiles import PROFILES
from wid.rolls import (
    RESOURCES_MAX,
    RESOURCES_MIN,
    STANDING_LABELS,
    STRAIN_ENDINGS,
    BonusKind,
    PowerMode,
    ResourceEffect,
)

# The terminal's Danger theme on paper, and a dark variant for browsers set to dark mode. The
# outcome colours are checked against the paper and the fields (tests/test_web_sheet.py).
COLOURS = {
    "light": {
        "paper": "#FBF8F1",
        "ink": "#2B2929",
        "band": "#2F2D2D",
        "band-ink": "#FBF8F1",
        "field": "#E6E3EC",
        "rule": "#CFCADB",
        "danger": "#B22222",
        "on-danger": "#FFFFFF",
        "hit": "#2E7D4F",
        "miss": "#8A5A00",
        "fumble": "#B22222",
    },
    "dark": {
        "paper": "#211E26",
        "ink": "#EEE9E0",
        "band": "#141217",
        "band-ink": "#EEE9E0",
        "field": "#2F2B36",
        "rule": "#4A4555",
        "danger": "#EF6A63",
        "on-danger": "#211E26",
        "hit": "#63C38D",
        "miss": "#E2AA55",
        "fumble": "#EF6A63",
    },
}


def css_variables(colours: dict[str, str]) -> str:
    return " ".join(f"--{name}: {value};" for name, value in colours.items())


# The terminal renders notes with Textual's "gfm-like" Markdown; the same preset here, with raw
# HTML escaped and images left out, so a note can neither inject markup nor fetch from the web.
MARKDOWN = MarkdownIt("gfm-like", {"html": False}).disable("image")


def open_links_elsewhere(renderer, tokens, index, options, env) -> str:
    # A link in the notes opens a new tab, so following it never leaves the game page.
    tokens[index].attrSet("target", "_blank")
    tokens[index].attrSet("rel", "noopener noreferrer")
    return renderer.renderToken(tokens, index, options, env)


MARKDOWN.add_render_rule("link_open", open_links_elsewhere)


def notes_html(text: str) -> str:
    return MARKDOWN.render(text)


def sheet_context(game: Game, message: str, *, preview: bool) -> dict[str, object]:
    """Everything the sheet template reads, worded by the same functions the terminal uses."""
    session = game.session
    result = session.current_result
    resources = ""
    if result is not None:
        resources = resources_line(
            result,
            total_strain=session.total_strain,
            total_corruption=session.total_corruption,
            tech_pieces=session.tech.pieces if session.tech else None,
        )
    return {
        "game": game,
        "session": session,
        "kit": game.profile,
        "kits": PROFILES,
        "message": message,
        "result": result,
        "resources": resources,
        "reminder": resources_reminder(result) if result is not None else "",
        "pool": pool_line(game.draft_request(preview=True)),
        "strain_title": strain_summary(session.strain),
        "strain_status": strain_status(session.strain),
        "corruption_status": corruption_status(session),
        "tech_line": tech_starting_line(session.tech),
        "history": [str(entry) for entry in reversed(game.history)],
        "preview": preview,
        "notes_html": notes_html(game.notes) if preview else "",
        "confirm": game.has_unsaved_state(),
        "bonus_labels": BONUS_LABELS,
        "item_kinds": (BonusKind.APPROPRIATE_ITEM, BonusKind.INAPPROPRIATE_ITEM),
        "BonusKind": BonusKind,
        "PowerMode": PowerMode,
        "ResourceEffect": ResourceEffect,
        "standing_labels": STANDING_LABELS,
        "strain_endings": STRAIN_ENDINGS,
        "resources_min": RESOURCES_MIN,
        "resources_max": RESOURCES_MAX,
    }
