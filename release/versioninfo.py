"""The text of the Windows version resource, from the installed package's version.

PyInstaller reads this file format on Windows. It is plain text, so it can be produced and
tested on any system without PyInstaller's own helper (which needs ``pefile``, Windows only).
"""

import re
from importlib.metadata import version

PRODUCT = "wid"
DESCRIPTION = "A terminal dice roller for We're in Danger"
LANGUAGE_CODE = "040904B0"  # US English, Unicode


def installed_version() -> str:
    """The version hatch-vcs gave the installed wid, taken from its git tag."""
    return version(PRODUCT)


def numeric_version(text: str) -> tuple[int, int, int, int]:
    """The four numbers Windows wants, from the release part only.

    ``0.1.0`` becomes ``(0, 1, 0, 0)``; a dev build such as ``0.1.1.dev3+gabc1234`` becomes
    ``(0, 1, 1, 0)``, since Windows file versions cannot hold the dev suffix.
    """
    release = re.match(r"\d+(?:\.\d+)*", text)
    numbers = [int(part) for part in release.group().split(".")[:4]] if release else []
    return tuple((numbers + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def version_file_text(text: str) -> str:
    numbers = numeric_version(text)
    strings = {
        "FileDescription": DESCRIPTION,
        "FileVersion": text,
        "InternalName": PRODUCT,
        "OriginalFilename": f"{PRODUCT}.exe",
        "ProductName": PRODUCT,
        "ProductVersion": text,
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
