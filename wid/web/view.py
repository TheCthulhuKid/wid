"""What the browser sheet shows: its colours, the notes preview and the template context."""

from markdown_it import MarkdownIt

from wid.dangers import DANGERS_MAX, PC_MAX, PC_MIN, DangerClass, Difficulty, classes_for
from wid.formatting import (
    BONUS_LABELS,
    CHARACTER_LABELS,
    CORRUPTION_AMOUNTS,
    LOADOUT_COLUMNS,
    NO_ACTIVATION_HINT,
    NO_RESULT_HINT,
    POWER_LABELS,
    RANKS_HINT,
    SPEND_LABELS,
    activation_line,
    corruption_status,
    danger_summary,
    loadout_rows,
    pool_line,
    resources_line,
    resources_reminder,
    result_text,
    scene_summary,
    strain_box_name,
    strain_status,
    strain_summary,
    summary_parts,
    tech_slot_label,
    tech_starting_line,
)
from wid.game import BaseGame, Game
from wid.gm import GmGame
from wid.history import history_statistics
from wid.profiles import PROFILES
from wid.rolls import (
    RANKS,
    RESOURCES_MAX,
    RESOURCES_MIN,
    SCARED_MAX,
    STANDING_LABELS,
    STRAIN_ENDINGS,
    BonusKind,
    PowerMode,
)
from wid.web.forms import NeedsConfirmation

# The terminal's Danger theme on paper, and a dark variant for dark mode or the page's switch. The
# outcome colours are checked against the paper the dice sit on (tests/test_web_sheet.py).
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


def session_context(
    game: BaseGame,
    message: str,
    *,
    preview: bool,
    ask: NeedsConfirmation | None = None,
    export_path: str = "",
) -> dict[str, object]:
    """What the session block, the history and the question dialog read, on either page."""
    return {
        "game": game,
        "kit": game.profile,
        "kits": PROFILES,
        "message": message,
        "savable": game.savable,
        "history": [str(entry) for entry in reversed(game.history)],
        "statistics": history_statistics(game.history),
        "preview": preview,
        "ask": ask,
        # What the player typed stays; the suggestion only fills an empty box.
        "export_path": export_path or game.default_export_path(),
        "notes_html": notes_html(game.notes) if preview else "",
    }


def sheet_context(
    game: Game,
    message: str,
    *,
    preview: bool,
    ask: NeedsConfirmation | None = None,
    export_path: str = "",
) -> dict[str, object]:
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
        **session_context(game, message, preview=preview, ask=ask, export_path=export_path),
        "sheet_template": "sheet.html",
        "session": session,
        "result": result,
        "resources": resources,
        "reminder": resources_reminder(result) if result is not None else "",
        "result_text": result_text(result) if result is not None else "",
        # The totals, each with its outcome for colour; the browser spaces them out instead of "|".
        "totals": [part for part in summary_parts(result) if part[1]] if result is not None else [],
        "pool": pool_line(game.draft_request(preview=True)),
        "strain_title": strain_summary(session.strain),
        "strain_status": strain_status(session.strain),
        "corruption_status": corruption_status(session),
        "tech_line": tech_starting_line(session.tech),
        "bonus_labels": BONUS_LABELS,
        "item_kinds": (BonusKind.APPROPRIATE_ITEM, BonusKind.INAPPROPRIATE_ITEM),
        "BonusKind": BonusKind,
        "PowerMode": PowerMode,
        "standing_labels": STANDING_LABELS,
        "strain_endings": STRAIN_ENDINGS,
        "resources_min": RESOURCES_MIN,
        "resources_max": RESOURCES_MAX,
        "scared_max": SCARED_MAX,
        "ranks": RANKS,
        "corruption_amounts": CORRUPTION_AMOUNTS,
        "power_labels": POWER_LABELS,
        "spend_labels": SPEND_LABELS,
        "character_labels": CHARACTER_LABELS,
        "ranks_hint": RANKS_HINT,
        "no_result_hint": NO_RESULT_HINT,
        "tech_slot_label": tech_slot_label,
        "strain_box_name": strain_box_name,
    }


def gm_context(
    game: GmGame,
    message: str,
    *,
    preview: bool,
    ask: NeedsConfirmation | None = None,
    export_path: str = "",
) -> dict[str, object]:
    """Everything the GM page reads: the scene, its Dangers and the last activation."""
    scene = game.scene
    activation = game.last_activation
    return {
        **session_context(game, message, preview=preview, ask=ask, export_path=export_path),
        "sheet_template": "gm.html",
        "scene": scene,
        "dangers": [
            danger_summary(danger, index, scene.pc_count)
            for index, danger in enumerate(scene.dangers)
        ],
        "scene_summary": scene_summary(scene),
        "activation": activation_line(activation) if activation else NO_ACTIVATION_HINT,
        "loadout_columns": LOADOUT_COLUMNS,
        "loadout_rows": loadout_rows(scene.loadout, game.genre),
        "classes": classes_for(game.genre),
        "difficulties": tuple(Difficulty),
        "default_class": DangerClass.BRUTE,
        "default_difficulty": Difficulty.COMPETENT,
        "pc_counts": range(PC_MIN, PC_MAX + 1),
        "amounts": range(1, 7),
        "scene_full": len(scene.dangers) >= DANGERS_MAX,
    }
