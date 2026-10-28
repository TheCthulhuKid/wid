import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, StrictBool

from wid.storage import write_text

IS_WINDOWS = sys.platform == "win32"


class Settings(BaseModel):
    """User preferences kept between runs; unknown keys are ignored.

    ``None`` means the user has not chosen, so the app uses its own default.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    theme: str | None = None
    tab: str | None = None
    strain_collapsed: StrictBool | None = None
    items_collapsed: StrictBool | None = None


def config_root() -> Path:
    """The folder that holds per-user program settings on this system.

    ``$XDG_CONFIG_HOME`` wins everywhere. Otherwise Windows uses ``%APPDATA%`` and other
    systems ``~/.config``. Raises ``OSError`` when there is no home directory to fall back on.
    """
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured)
    appdata = os.environ.get("APPDATA")
    if IS_WINDOWS and appdata:
        return Path(appdata)
    try:
        home = Path.home()
    except RuntimeError as error:
        raise OSError("Could not determine the home directory") from error
    return home / "AppData" / "Roaming" if IS_WINDOWS else home / ".config"


def settings_path() -> Path:
    return config_root() / "wid" / "settings.json"


def recovery_path() -> Path | None:
    """Where the game is kept while it has unsaved changes, in case wid closes without a save.

    None when there is no home directory to keep it in; wid then plays without a copy.
    """
    return recovery_file("recovery.json")


def gm_recovery_path() -> Path | None:
    """The GM mode's own copy, so a GM and a player on one computer never overwrite each other's."""
    return recovery_file("gm-recovery.json")


def recovery_file(name: str) -> Path | None:
    try:
        return config_root() / "wid" / name
    except OSError:
        return None


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
