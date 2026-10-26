import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "release"))

import versioninfo  # noqa: E402

from wid.cli import package_version  # noqa: E402


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
        ("0.1.1.dev3+gabc1234", (0, 1, 1, 0)),
    ],
)
def test_numeric_version_keeps_only_the_release_numbers(version, expected):
    assert versioninfo.numeric_version(version) == expected


def test_the_version_is_the_installed_one_the_program_reports():
    assert versioninfo.installed_version() == package_version()


def test_generated_text_is_valid_and_carries_the_product_details():
    text = versioninfo.version_file_text("0.1.1.dev3+gabc1234")

    info = parse(text)
    fixed = info.kwargs["ffi"].kwargs
    assert fixed["filevers"] == fixed["prodvers"] == (0, 1, 1, 0)
    for expected in (
        "'ProductName', 'wid'",
        "'OriginalFilename', 'wid.exe'",
        "'ProductVersion', '0.1.1.dev3+gabc1234'",
        '"A terminal dice roller for We\'re in Danger"',
    ):
        assert expected in text
