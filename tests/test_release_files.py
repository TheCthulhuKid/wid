import ast
import struct
from pathlib import Path

import pytest

RELEASE = Path(__file__).resolve().parents[1] / "release"
SPEC = RELEASE / "wid.spec"
ICON = RELEASE / "wid.ico"


def icon_images():
    data = ICON.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    images = []
    for index in range(count):
        width, height, _, _, _, _, size, offset = struct.unpack(
            "<BBBBHHII", data[6 + 16 * index : 22 + 16 * index]
        )
        images.append((width or 256, height or 256, size, offset))
    return reserved, kind, images, len(data)


def test_spec_is_valid_python_and_names_the_release_files():
    source = SPEC.read_text(encoding="utf-8")

    ast.parse(source)

    assert "wid_entry.py" in source
    assert (RELEASE / "wid_entry.py").is_file()
    assert "wid.ico" in source


def test_spec_gives_the_icon_to_windows_builds_only():
    source = SPEC.read_text(encoding="utf-8")

    assert 'if sys.platform == "win32" else None' in source


def test_icon_is_a_well_formed_ico_file():
    reserved, kind, images, length = icon_images()

    assert (reserved, kind) == (0, 1)
    assert images
    for _, _, size, offset in images:
        assert offset + size <= length


def test_icon_has_a_large_image_for_modern_windows():
    sizes = {(width, height) for width, height, _, _ in icon_images()[2]}

    assert (256, 256) in sizes


class Recorder:
    """Stands in for a PyInstaller build class and remembers how it was called."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    def __getattr__(self, name):
        return []  # the pure, scripts, binaries and datas lists of an Analysis result


def run_spec(monkeypatch, tmp_path, platform, onedir=None):
    """Execute release/wid.spec with PyInstaller's build classes replaced by recorders."""
    import sys
    import types

    hooks = types.ModuleType("PyInstaller.utils.hooks")
    hooks.collect_data_files = lambda package: [(f"{package}.data", package)]
    hooks.collect_submodules = lambda package: [f"{package}.sub"]
    hooks.copy_metadata = lambda package: [(f"{package}.dist-info", package)]
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "path", list(sys.path))
    if onedir is None:
        monkeypatch.delenv("WID_ONEDIR", raising=False)
    else:
        monkeypatch.setenv("WID_ONEDIR", "1" if onedir else "0")
    namespace = {
        "SPECPATH": str(RELEASE),
        "workpath": str(tmp_path / "work"),
        "Analysis": Recorder,
        "PYZ": Recorder,
        "EXE": Recorder,
        "COLLECT": Recorder,
    }
    exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), namespace)  # noqa: S102
    return namespace


def test_windows_build_gets_the_icon_and_a_version_file(monkeypatch, tmp_path):
    namespace = run_spec(monkeypatch, tmp_path, "win32")

    options = namespace["exe_options"]
    assert options["icon"].endswith("wid.ico")
    version_file = Path(options["version"])
    assert version_file.parent == tmp_path / "work"
    text = version_file.read_text(encoding="utf-8")
    assert "StringStruct('ProductName', 'wid')" in text
    assert "StringStruct('OriginalFilename', 'wid.exe')" in text
    assert options["console"] is True


def test_other_systems_get_neither_icon_nor_version_file(monkeypatch, tmp_path):
    namespace = run_spec(monkeypatch, tmp_path, "linux")

    options = namespace["exe_options"]
    assert options["icon"] is None
    assert options["version"] is None
    assert not (tmp_path / "work").exists()


def test_the_spec_bundles_the_data_textual_and_wid_need(monkeypatch, tmp_path):
    namespace = run_spec(monkeypatch, tmp_path, "linux")

    datas = [name for name, _ in namespace["datas"]]
    assert {"wid.data", "textual.data", "wid.dist-info", "textual.dist-info"} <= set(datas)
    assert "textual.sub" in namespace["hiddenimports"]
    assert "uvicorn.sub" in namespace["hiddenimports"]


@pytest.mark.parametrize(
    ("platform", "default_folder"), [("win32", True), ("linux", False), ("darwin", False)]
)
def test_windows_builds_a_folder_and_other_systems_one_file_by_default(
    monkeypatch, tmp_path, platform, default_folder
):
    assert run_spec(monkeypatch, tmp_path, platform)["ONEDIR"] is default_folder


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_the_environment_variable_overrides_the_default(monkeypatch, tmp_path, platform):
    assert run_spec(monkeypatch, tmp_path, platform, onedir=True)["ONEDIR"] is True
    assert run_spec(monkeypatch, tmp_path, platform, onedir=False)["ONEDIR"] is False
