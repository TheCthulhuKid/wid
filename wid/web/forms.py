"""What the browser sends: the sheet's fields, and the game action each request asks for.

Every action posts the whole sheet form, so the fields are copied into the game first (as the
terminal's ``collect`` does) and the action then runs on an up-to-date game. The player's page
and the GM's page each have their own ``collect`` and action table, sharing the session actions.
"""

from collections.abc import Callable, Sequence
from typing import NamedTuple
from urllib.parse import parse_qs

from wid.dangers import DangerClass, Difficulty
from wid.formatting import (
    GM_KIT_QUESTION,
    NEW_CHARACTER_QUESTION,
    NEW_GAME_QUESTION,
    RECOVERY_QUESTION,
    load_question,
    recovery_decline,
    replace_question,
)
from wid.game import BaseGame, Game, NameField
from wid.gm import GmGame
from wid.profiles import Genre
from wid.rolls import BonusKind, PowerMode, ResourceEffect
from wid.sessions import CharacterDetails


class Answer(NamedTuple):
    """One button of a question: its label, and the field it sends with the action again."""

    label: str
    name: str
    value: str = "1"


class NeedsConfirmation(Exception):
    """An action that would replace something; the sheet asks, then sends ``action`` again
    with the chosen answer's field set (the browser's version of the terminal's questions).

    A single ``flag`` makes a yes-or-no question; ``answers`` gives one button per answer.
    """

    def __init__(
        self,
        question: str,
        action: str,
        flag: str = "confirm",
        value: str = "1",
        *,
        confirm: str = "Replace",
        cancel: str = "Cancel",
        answers: Sequence[Answer] = (),
        carry: dict[str, str] | None = None,
    ):
        super().__init__(question)
        self.question = question
        self.action = action
        self.answers = tuple(answers) or (Answer(confirm, flag, value),)
        self.cancel = cancel
        # Fields the page no longer holds that the confirmed action needs again (an upload).
        self.carry = carry or {}


def as_number(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be a number.") from None


class SheetForm:
    """The URL-encoded fields of one request.

    Browsers send simple forms URL-encoded, so the standard library reads them. An uploaded save
    comes as text too: the page reads the file and sends it in a field, so no multipart parser
    is needed.
    """

    def __init__(self, body: bytes):
        self.fields = parse_qs(body.decode(), keep_blank_values=True)

    def get(self, name: str) -> str | None:
        values = self.fields.get(name)
        return values[0] if values else None

    def text(self, name: str) -> str:
        return self.get(name) or ""

    def number(self, name: str) -> int:
        return as_number(name, self.text(name))

    def numbers(self, name: str) -> list[int]:
        return [as_number(name, value) for value in self.fields.get(name, [])]

    def ticked(self, name: str) -> bool:
        return name in self.fields

    @property
    def has_sheet(self) -> bool:
        """Whether the sheet came along; only then does an unticked box mean "off"."""
        return "sheet" in self.fields


def take_numbered(
    form: SheetForm, prefix: str, count: int, apply: Callable[[int, str], object]
) -> None:
    """Pass the fields ``prefix-0``, ``prefix-1``... to ``apply``, one per numbered slot."""
    for index in range(count):
        if (value := form.get(f"{prefix}-{index}")) is not None:
            apply(index, value)


def collect(game: Game, form: SheetForm) -> None:
    """Copy the sheet's fields into the game; fields the request did not send are left alone.

    The typed text goes in first, then the choices are all checked before any is applied, so a
    bad choice (one the page never offers) is refused without losing what the player wrote.
    """
    if not form.has_sheet:
        return

    def take(name: str, apply: Callable[[str], object]) -> None:
        if (value := form.get(name)) is not None:
            apply(value)

    session = game.session
    details = {field: form.get(f"character-{field}") for field in CharacterDetails.model_fields}
    game.character = game.character.model_copy(
        update={field: value for field, value in details.items() if value is not None}
    )
    take("session-name", lambda value: setattr(game, "name", value))
    take("session-path", lambda value: setattr(game, "path", value))
    take("notes", lambda value: setattr(game, "notes", value))
    for kind in BonusKind:
        take(f"name-{kind}", lambda value, kind=kind: game.rename("bonus", kind, value))
    # The counts come from the character, so a kit's slots exist only where it has them (Tech in
    # Second Contact, manifestations in Oldheart), and the page sends only its kit's fields.
    slots: dict[NameField, int] = {
        "power": len(session.power_names),
        "manifestation": len(session.manifestations),
        "tech": len(session.tech.pieces) if session.tech else 0,
        "strain": len(session.strain.names),
    }
    for field, count in slots.items():
        take_numbered(
            form,
            f"{field}-name",
            count,
            lambda index, value, field=field: game.rename(field, index, value),
        )

    game.set_test_options(
        fear_level=form.number("fear") if form.get("fear") else game.fear_level,
        assisted=form.ticked("assisted"),
        expertise=form.ticked("expertise"),
        power=PowerMode(form.get("power") or game.power),
        reroll=form.numbers("reroll"),
        item_target=form.number("die") if form.get("die") is not None else game.item_target,
    )


SAVE_FIRST = "save-first"


def chosen_kit(form: SheetForm, answers: dict[str, str]) -> tuple[Genre, str | None]:
    """The kit picked, and the answer to the kit question when one was given.

    The sheet shows the old kit again while asking, so each answer carries the new one.
    """
    for name in (SAVE_FIRST, *answers):
        if (value := form.get(name)) is not None:
            return Genre(value), name
    return Genre(form.text("genre")), None


def kit_question(
    question: str, genre: Genre, answers: dict[str, str], cancel: str
) -> NeedsConfirmation:
    buttons = [Answer("Save first", SAVE_FIRST, genre)]
    buttons += [Answer(label, name, genre) for name, label in answers.items()]
    return NeedsConfirmation(question, "change-kit", answers=buttons, cancel=cancel)


def save_first(game: BaseGame, form: SheetForm, genre: Genre) -> str:
    """Save before changing kit; a question about replacing the file keeps the kit change."""
    try:
        return save(game, form)
    except NeedsConfirmation as question:
        raise NeedsConfirmation(
            question.question, "change-kit", "overwrite", carry={SAVE_FIRST: genre}
        ) from None


PLAYER_KIT_ANSWERS = {"confirm-genre": "Start new game"}


def change_kit(game: Game, form: SheetForm) -> str:
    genre, answer = chosen_kit(form, PLAYER_KIT_ANSWERS)
    if genre == game.session.profile_id:
        return ""
    if answer is None and game.has_unsaved_state():
        raise kit_question(NEW_GAME_QUESTION, genre, PLAYER_KIT_ANSWERS, "Keep current game")
    saved = save_first(game, form, genre) if answer == SAVE_FIRST else ""
    return f"{saved} {game.change_kit(genre)}".strip()


GM_KIT_ANSWERS = {"keep-scene": "Keep scene", "start-new": "Start new"}


def change_gm_kit(game: GmGame, form: SheetForm) -> str:
    """After Save first nothing is left to lose, so the scene is kept, as the terminal does."""
    genre, answer = chosen_kit(form, GM_KIT_ANSWERS)
    if genre == game.genre:
        return ""
    if answer is None and game.has_unsaved_state():
        raise kit_question(GM_KIT_QUESTION, genre, GM_KIT_ANSWERS, "Cancel")
    saved = save_first(game, form, genre) if answer == SAVE_FIRST else ""
    changed = game.start_new(genre) if answer == "start-new" else game.keep_scene(genre)
    return f"{saved} {changed}".strip()


def recovery_question(game: BaseGame) -> NeedsConfirmation | None:
    """On opening the page, offer back the game an earlier run closed without saving."""
    if not game.recovery_available():
        return None
    decline = recovery_decline(opened=bool(game.path))
    return NeedsConfirmation(
        RECOVERY_QUESTION, "restore", "confirm", confirm="Restore", cancel=decline
    )


def new_character(game: Game, form: SheetForm) -> str:
    if not form.ticked("confirm") and game.has_unsaved_state():
        raise NeedsConfirmation(NEW_CHARACTER_QUESTION, "new-character", "confirm")
    return game.new_character()


def save(game: BaseGame, form: SheetForm) -> str:
    try:
        return game.save(overwrite=form.ticked("overwrite"))
    except FileExistsError as error:
        question = replace_question("save", error.filename)
        raise NeedsConfirmation(question, "save", "overwrite") from error


def load(game: BaseGame, form: SheetForm) -> str:
    saved, path = game.read_save(form.text("session-path"))
    if game.has_unsaved_state() and not form.ticked("confirm"):
        raise NeedsConfirmation(load_question(saved.name), "load", "confirm")
    return game.load(saved, path)


def upload(game: BaseGame, form: SheetForm) -> str:
    text = form.text("session-file")
    saved = game.read_save_text(text)
    if game.has_unsaved_state() and not form.ticked("confirm"):
        question = load_question(saved.name)
        raise NeedsConfirmation(question, "upload", "confirm", carry={"session-file": text})
    return game.load(saved, None)


def export(game: BaseGame, form: SheetForm) -> str:
    try:
        return game.export_history(form.text("export-path"), overwrite=form.ticked("overwrite"))
    except FileExistsError as error:
        question = replace_question("file", error.filename)
        raise NeedsConfirmation(question, "export", "overwrite") from error


# The route names both pages have, as in ``POST /actions/<name>``, and the game call each makes.
SESSION_ACTIONS: dict[str, Callable[[BaseGame, SheetForm], str]] = {
    "undo": lambda game, form: game.undo(),
    "roll-d6": lambda game, form: game.roll_one_die(),
    "restore": lambda game, form: game.restore_recovery(),
    # Shows the sheet again with the fields taken in, for changes such as Scared or the notes
    # preview that alter what the sheet shows without being a game action.
    "update": lambda game, form: "",
    "save": save,
    "load": load,
    "upload": upload,
    "export": export,
}

# The player's page.
ACTIONS: dict[str, Callable[[Game, SheetForm], str]] = {
    **SESSION_ACTIONS,
    "start-game": lambda game, form: game.start_game(tuple(form.numbers("rank"))),
    "roll": lambda game, form: game.roll(form.get("attribute")),
    "reroll": lambda game, form: game.reroll(set(form.numbers("reroll"))),
    "apply-bonus": lambda game, form: game.apply_bonus(
        BonusKind(form.text("kind")), form.number("die")
    ),
    "apply-tech": lambda game, form: game.apply_tech(form.number("index"), form.number("die")),
    "strain-box": lambda game, form: game.set_strain_box(
        form.number("index"), form.ticked("marked")
    ),
    "take-strain": lambda game, form: game.take_strain(),
    "take-wound": lambda game, form: game.take_wound(),
    "new-scenario": lambda game, form: game.start_scenario(),
    "sacrifice-tech": lambda game, form: game.sacrifice_tech(form.number("index")),
    "resources": lambda game, form: game.adjust_resources(form.number("amount")),
    "spend-resources": lambda game, form: game.spend_resources(ResourceEffect(form.text("effect"))),
    "lose-crafted-item": lambda game, form: game.lose_crafted_item(),
    "gain-corruption": lambda game, form: game.gain_corruption(form.number("corruption-amount")),
    "add-manifestation": lambda game, form: game.add_manifestation(),
    "remove-manifestation": lambda game, form: game.remove_manifestation(),
    "standing": lambda game, form: game.set_standing(form.number("standing")),
    "new-character": new_character,
    "change-kit": change_kit,
}


def collect_gm(game: GmGame, form: SheetForm) -> None:
    """Copy the GM page's fields into the game: the session text and the Dangers' names."""
    if not form.has_sheet:
        return
    for name, apply in (
        ("session-name", lambda value: setattr(game, "name", value)),
        ("session-path", lambda value: setattr(game, "path", value)),
        ("notes", lambda value: setattr(game, "notes", value)),
    ):
        if (value := form.get(name)) is not None:
            apply(value)
    take_numbered(form, "danger-name", len(game.scene.dangers), game.rename_danger)


# The GM's page.
GM_ACTIONS: dict[str, Callable[[GmGame, SheetForm], str]] = {
    **SESSION_ACTIONS,
    "set-pcs": lambda game, form: game.set_pc_count(form.number("pcs")),
    "add-danger": lambda game, form: game.add_danger(
        form.text("new-danger-name"),
        DangerClass(form.text("danger-class")),
        Difficulty(form.text("difficulty")),
    ),
    "remove-danger": lambda game, form: game.remove_danger(form.number("index")),
    "commit-hits": lambda game, form: game.commit_hits(form.number("amount")),
    "raise-threshold": lambda game, form: game.raise_threshold(form.number("amount")),
    "hostile": lambda game, form: game.set_hostile(form.ticked("hostile")),
    "activate": lambda game, form: game.activate(),
    "clash": lambda game, form: game.clash(),
    "change-kit": change_gm_kit,
}
