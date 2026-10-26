# PyInstaller spec for the wid release. Build from the repository root:
#   uv run pyinstaller release/wid.spec --noconfirm
# Windows builds a folder by default and other systems a single file: a one-file program
# unpacks itself on every start, which took 2.3 s on Windows against 1.0 s for the folder.
# Set WID_ONEDIR=1 or WID_ONEDIR=0 to choose.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(Path(SPECPATH)))  # for versioninfo.py next to this file

from versioninfo import installed_version, version_file_text  # noqa: E402
ONEDIR = os.environ.get("WID_ONEDIR", "1" if sys.platform == "win32" else "0") == "1"
ICON = ROOT / "release" / "wid.ico"

# Data files read at run time: wid's stylesheet and Textual's own files. Package metadata
# is what makes `wid --version` and Textual's version lookup work in the frozen program.
datas = [
    *collect_data_files("wid"),
    *collect_data_files("textual"),
    *copy_metadata("wid"),
    *copy_metadata("textual"),
]

# Textual imports widgets, drivers and parsers by name, and Rich loads its Unicode tables
# the same way, so PyInstaller cannot find them by reading the code.
hiddenimports = [
    *collect_submodules("textual"),
    *collect_submodules("rich._unicode_data"),
]

analysis = Analysis(
    [str(ROOT / "release" / "wid_entry.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
)
archive = PYZ(analysis.pure)

# The file properties Windows shows (product name, description, version), from the git tag.
version_file = None
if sys.platform == "win32":
    version_file = Path(workpath) / "wid_version_info.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(version_file_text(installed_version()), encoding="utf-8")

exe_options = dict(
    name="wid",
    console=True,
    upx=False,
    icon=str(ICON) if sys.platform == "win32" else None,
    version=str(version_file) if version_file else None,
)

if ONEDIR:
    exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, **exe_options)
    COLLECT(exe, analysis.binaries, analysis.datas, name="wid", upx=False)
else:
    EXE(archive, analysis.scripts, analysis.binaries, analysis.datas, [], **exe_options)
