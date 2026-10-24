import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wid.storage import write_text


class Settings(BaseModel):
    """User preferences kept between runs; unknown keys are ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    theme: str | None = None


def settings_path() -> Path:
    """Where settings live: ``$XDG_CONFIG_HOME/wid/settings.json``, else ``~/.config/wid/``.

    Raises ``OSError`` when there is no home directory to fall back on.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "wid" / "settings.json"
    try:
        return Path.home() / ".config" / "wid" / "settings.json"
    except RuntimeError as error:
        raise OSError("Could not determine the home directory") from error


def load_settings(path: Path | None = None) -> Settings:
    """Read settings, returning defaults when the file is missing, unreadable or invalid."""
    try:
        text = (path or settings_path()).read_text(encoding="utf-8")
        return Settings.model_validate_json(text)
    except (OSError, ValueError):
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write settings, creating the directory; raises ``OSError`` if that is impossible."""
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, settings.model_dump_json(indent=2), overwrite=True)
