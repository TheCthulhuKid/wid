from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class ConfirmReset(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static(
                "Changing genre discards current kit resources, strain boxes, "
                "wound/defeat names, and the active test."
            )
            yield Button("Discard and switch", id="confirm-reset", variant="warning")
            yield Button("Keep current genre", id="cancel-reset")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-reset")


class ConfirmSessionAction(ModalScreen[bool]):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static(self.message, markup=False)
            yield Button("Replace", id="confirm-session", variant="warning")
            yield Button("Cancel", id="cancel-session")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-session")


class LoadGame(ModalScreen[str | None]):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        with Vertical(id="load-dialog"):
            yield Label("Load game — file path (JSON)")
            yield Input(self.path, placeholder="/path/to/session.json", id="load-path")
            yield Button("Load game", id="submit-load", variant="primary")
            yield Button("Cancel", id="cancel-load")

    def on_mount(self) -> None:
        self.query_one("#load-path", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(
            self.query_one("#load-path", Input).value if event.button.id == "submit-load" else None
        )
