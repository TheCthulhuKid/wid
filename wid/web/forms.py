"""What the browser sends: the sheet's fields, and the game action each request asks for.

Every action posts the whole sheet form, so the fields are copied into the game first (as the
terminal's ``collect`` does) and the action then runs on an up-to-date game.
"""

from collections.abc import Callable
from urllib.parse import parse_qs

from wid.game import Game
from wid.profiles import Genre
from wid.rolls import BonusKind, PowerMode, ResourceEffect
from wid.sessions import CharacterDetails


class NeedsConfirmation(Exception):
    """An action that would replace something; the sheet asks, then sends ``action`` again
    with ``flag`` set (the browser's version of the terminal's confirmation screens)."""

    def __init__(self, question: str, action: str, flag: str):
        super().__init__(question)
        self.question = question
        self.action = action
        self.flag = flag


class SheetForm:
    """The URL-encoded fields of one request.

    Browsers send simple forms URL-encoded, so the standard library reads them; only file
    uploads would need a multipart parser.
    """

    def __init__(self, body: bytes):
        self.fields = parse_qs(body.decode(), keep_blank_values=True)

    def get(self, name: str) -> str | None:
        values = self.fields.get(name)
        return values[0] if values else None

    def text(self, name: str) -> str:
        return self.get(name) or ""

    def number(self, name: str) -> int:
        return int(self.text(name))

    def numbers(self, name: str) -> list[int]:
        return [int(value) for value in self.fields.get(name, [])]

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
    """Copy the sheet's fields into the game; fields the request did not send are left alone."""
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
    take("fear", lambda value: setattr(game, "fear_level", int(value)))
    take("power", lambda value: setattr(game, "power", PowerMode(value)))
    game.assisted = form.ticked("assisted")
    game.expertise = form.ticked("expertise")
    game.reroll_selection = tuple(form.numbers("reroll"))
    take("die", lambda value: setattr(game, "item_target", int(value)))
    for kind in BonusKind:
        take(f"name-{kind}", lambda value, kind=kind: session.set_bonus_name(kind, value))
    # The counts come from the character, so a kit's slots exist only where it has them (Tech in
    # Second Contact, manifestations in Oldheart), and the page sends only its kit's fields.
    take_numbered(form, "power-name", len(session.power_names), session.set_power_name)
    manifestations = len(session.manifestations)
    take_numbered(form, "manifestation-name", manifestations, session.set_manifestation_name)
    tech_slots = len(session.tech.pieces) if session.tech else 0
    take_numbered(form, "tech-name", tech_slots, session.set_tech_name)
    take_numbered(form, "strain-name", len(session.strain.names), session.set_strain_name)


def save(game: Game, form: SheetForm) -> str:
    try:
        return game.save(overwrite=form.ticked("overwrite"))
    except FileExistsError as error:
        question = f"Replace the existing save at {error.filename}?"
        raise NeedsConfirmation(question, "save", "overwrite") from error


def load(game: Game, form: SheetForm) -> str:
    saved, path = game.read_save(form.text("session-path"))
    if game.has_unsaved_state() and not form.ticked("confirm"):
        question = (
            f"Load {saved.name}? This replaces the current game and history. "
            "Unsaved changes will be lost."
        )
        raise NeedsConfirmation(question, "load", "confirm")
    return game.load(saved, path)


def export(game: Game, form: SheetForm) -> str:
    try:
        return game.export_history(form.text("export-path"), overwrite=form.ticked("overwrite"))
    except FileExistsError as error:
        question = f"Replace the existing file at {error.filename}?"
        raise NeedsConfirmation(question, "export", "overwrite") from error


# Each route name, as in ``POST /actions/<name>``, and the game call it makes.
ACTIONS: dict[str, Callable[[Game, SheetForm], str]] = {
    "start-game": lambda game, form: game.start_game(tuple(form.numbers("rank"))),
    "roll": lambda game, form: game.roll(form.get("attribute")),
    "reroll": lambda game, form: game.reroll(set(form.numbers("reroll"))),
    "apply-bonus": lambda game, form: game.apply_bonus(
        BonusKind(form.text("kind")), form.number("die")
    ),
    "apply-tech": lambda game, form: game.apply_tech(form.number("index"), form.number("die")),
    "undo-bonus": lambda game, form: game.undo_bonus(),
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
    "roll-d6": lambda game, form: game.roll_one_die(),
    "new-character": lambda game, form: game.new_character(),
    "change-kit": lambda game, form: game.change_kit(Genre(form.text("genre"))),
    # Shows the sheet again with the fields taken in, for changes such as Scared or the notes
    # preview that alter what the sheet shows without being a game action.
    "update": lambda game, form: "",
    "save": save,
    "load": load,
    "export": export,
}
