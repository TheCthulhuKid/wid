from collections.abc import Sequence
from typing import ClassVar, NamedTuple

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from wid.formatting import SPEND_LABELS
from wid.rolls import RESOURCES_MAX, ResourceEffect


class Answer(NamedTuple):
    """One button of a question: the id the dialog dismisses with, its label and its look."""

    id: str
    label: str
    variant: str = "default"


CONFIRM = "confirm-session"
CANCEL = "cancel-session"
SAVE_FIRST = Answer("save-first", "Save first")


class Question(ModalScreen[str]):
    """Ask ``message`` with any number of answers; dismisses with the chosen answer's id."""

    def __init__(self, message: str, answers: Sequence[Answer]):
        super().__init__()
        self.message = message
        self.answers = tuple(answers)

    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static(self.message, markup=False)
            for answer in self.answers:
                yield Button(answer.label, id=answer.id, variant=answer.variant)

    # Textual runs the handler of every class that defines one, so only this class has it.
    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(self.result(event.button.id))

    def result(self, answer: str) -> object:
        return answer


class ConfirmSessionAction(Question):
    """A yes-or-no question; dismisses with whether the player confirmed."""

    def __init__(self, message: str, confirm: str = "Replace", cancel: str = "Cancel"):
        super().__init__(message, (Answer(CONFIRM, confirm, "warning"), Answer(CANCEL, cancel)))

    def result(self, answer: str) -> bool:
        return answer == CONFIRM


class SpendResources(ModalScreen[ResourceEffect | None]):
    """Choose what a full pool of Resources buys; dismisses with ``None`` when cancelled."""

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="spend-dialog"):
            yield Label(f"Spend {RESOURCES_MAX} Resources on:")
            for effect, label in SPEND_LABELS.items():
                yield Button(label, id=f"spend-{effect.value}")
            yield Button("Cancel", id="cancel-spend")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        chosen = event.button.id.removeprefix("spend-")
        self.dismiss(ResourceEffect(chosen) if chosen in set(ResourceEffect) else None)


class PathPrompt(ModalScreen[str | None]):
    """Ask for a file path; dismisses with the path, or ``None`` when cancelled."""

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]
    prefix: ClassVar[str]
    heading: ClassVar[str]
    placeholder: ClassVar[str]
    action: ClassVar[str]

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        with Vertical(id=f"{self.prefix}-dialog"):
            yield Label(self.heading)
            yield Input(self.path, placeholder=self.placeholder, id=f"{self.prefix}-path")
            yield Button(self.action, id=f"submit-{self.prefix}", variant="primary")
            yield Button("Cancel", id=f"cancel-{self.prefix}")

    def on_mount(self) -> None:
        self.query_one(f"#{self.prefix}-path", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        submitted = event.button.id == f"submit-{self.prefix}"
        self.dismiss(self.query_one(f"#{self.prefix}-path", Input).value if submitted else None)


class LoadGame(PathPrompt):
    prefix = "load"
    heading = "Load session — file path (JSON)"
    placeholder = "/path/to/session.json"
    action = "Load session"


class ExportHistory(PathPrompt):
    prefix = "export"
    heading = "Export history — file path (Markdown)"
    placeholder = "/path/to/history.md"
    action = "Export history"
