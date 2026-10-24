import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "release"))

import versioninfo  # noqa: E402


class Record:
    """Stands in for each class PyInstaller's version file refers to."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


def parse(text):
    names = (
        "VSVersionInfo FixedFileInfo StringFileInfo StringTable StringStruct VarFileInfo VarStruct"
    ).split()
    return eval(text, {name: Record for name in names})  # noqa: S307 - our own generated text


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.1.0", (0, 1, 0, 0)),
        ("1.2.3.4", (1, 2, 3, 4)),
        ("2", (2, 0, 0, 0)),
        ("1.0.0rc1", (1, 0, 0, 1)),
    ],
)
def test_numeric_version_has_four_parts(version, expected):
    assert versioninfo.numeric_version(version) == expected


def test_version_comes_from_pyproject():
    assert versioninfo.project_version(ROOT / "pyproject.toml") == "0.1.0"


def test_generated_text_is_valid_and_carries_the_product_details():
    text = versioninfo.version_file_text("0.1.0")

    info = parse(text)
    fixed = info.kwargs["ffi"].kwargs
    assert fixed["filevers"] == fixed["prodvers"] == (0, 1, 0, 0)
    for expected in (
        "'ProductName', 'wid'",
        "'OriginalFilename', 'wid.exe'",
        "'FileVersion', '0.1.0'",
        "'ProductVersion', '0.1.0'",
        '"A terminal dice roller for We\'re in Danger"',
    ):
        assert expected in text


def test_generated_text_matches_the_current_project_version():
    version = versioninfo.project_version(ROOT / "pyproject.toml")

    assert f"'ProductVersion', '{version}'" in versioninfo.version_file_text(version)
