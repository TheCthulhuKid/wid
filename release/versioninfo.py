"""The text of the Windows version resource, from ``pyproject.toml``.

PyInstaller reads this file format on Windows. It is plain text, so it can be produced and
tested on any system without PyInstaller's own helper (which needs ``pefile``, Windows only).
"""

import re
import tomllib
from pathlib import Path

PRODUCT = "wid"
DESCRIPTION = "A terminal dice roller for We're in Danger"
LANGUAGE_CODE = "040904B0"  # US English, Unicode


def project_version(pyproject: Path) -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def numeric_version(version: str) -> tuple[int, int, int, int]:
    """The four-part number Windows wants: ``0.1.0`` becomes ``(0, 1, 0, 0)``."""
    numbers = [int(part) for part in re.findall(r"\d+", version)[:4]]
    return tuple((numbers + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def version_file_text(version: str) -> str:
    numbers = numeric_version(version)
    strings = {
        "FileDescription": DESCRIPTION,
        "FileVersion": version,
        "InternalName": PRODUCT,
        "OriginalFilename": f"{PRODUCT}.exe",
        "ProductName": PRODUCT,
        "ProductVersion": version,
    }
    pairs = ",\n        ".join(
        f"StringStruct({key!r}, {value!r})" for key, value in strings.items()
    )
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers!r},
    prodvers={numbers!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable({LANGUAGE_CODE!r}, [
        {pairs}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
