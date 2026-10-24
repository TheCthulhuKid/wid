from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmShuffle(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation"):
            yield Static("Return all dealt cards, clear the ace tracker, and shuffle?")
            yield Button("Restore & shuffle", id="confirm-shuffle", variant="warning")
            yield Button("Cancel", id="cancel-shuffle")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-shuffle")
