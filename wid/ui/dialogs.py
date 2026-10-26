from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from wid.formatting import NEW_GAME_QUESTION, SPEND_EFFECTS
from wid.rolls import RESOURCES_MAX, ResourceEffect


class ConfirmReset(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static(NEW_GAME_QUESTION)
            yield Button("Start new game", id="confirm-reset", variant="warning")
            yield Button("Keep current game", id="cancel-reset")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-reset")


class ConfirmSessionAction(ModalScreen[bool]):
    def __init__(self, message: str, confirm: str = "Replace"):
        super().__init__()
        self.message = message
        self.confirm = confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static(self.message, markup=False)
            yield Button(self.confirm, id="confirm-session", variant="warning")
            yield Button("Cancel", id="cancel-session")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-session")


class SpendResources(ModalScreen[ResourceEffect | None]):
    """Choose what a full pool of Resources buys; dismisses with ``None`` when cancelled."""

    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="spend-dialog"):
            yield Label(f"Spend {RESOURCES_MAX} Resources on:")
            for effect, label in SPEND_EFFECTS.items():
                yield Button(label.capitalize(), id=f"spend-{effect.value}")
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
    heading = "Load game — file path (JSON)"
    placeholder = "/path/to/session.json"
    action = "Load game"


class ExportHistory(PathPrompt):
    prefix = "export"
    heading = "Export history — file path (Markdown)"
    placeholder = "/path/to/history.md"
    action = "Export history"
