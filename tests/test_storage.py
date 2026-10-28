import os

import pytest
from helpers import posix_only

from wid.storage import write_text


def names(directory):
    return sorted(path.name for path in directory.iterdir())


def test_writes_a_new_file_and_refuses_to_replace_it_unless_asked(tmp_path):
    path = tmp_path / "data.json"
    write_text(path, "first")
    assert path.read_text(encoding="utf-8") == "first"
    assert names(tmp_path) == ["data.json"]

    with pytest.raises(FileExistsError):
        write_text(path, "second")
    assert path.read_text(encoding="utf-8") == "first"
    assert names(tmp_path) == ["data.json"]

    write_text(path, "second", overwrite=True)
    assert path.read_text(encoding="utf-8") == "second"


@posix_only
def test_new_file_follows_umask_and_overwrite_keeps_mode(tmp_path):
    path = tmp_path / "data.json"
    old = os.umask(0o022)
    try:
        write_text(path, "first")
    finally:
        os.umask(old)
    assert path.stat().st_mode & 0o777 == 0o644

    path.chmod(0o664)
    write_text(path, "second", overwrite=True)
    assert path.stat().st_mode & 0o777 == 0o664


def test_works_without_hard_links_or_chmod_and_a_failed_fallback_leaves_no_file(
    tmp_path, monkeypatch
):
    def refuse(*args):
        raise PermissionError("unsupported")

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("wid.storage.os.link", refuse)
    monkeypatch.setattr("wid.storage.os.chmod", refuse)
    path = tmp_path / "data.json"

    write_text(path, "first")
    with pytest.raises(FileExistsError):
        write_text(path, "second")
    assert path.read_text(encoding="utf-8") == "first"
    assert names(tmp_path) == ["data.json"]

    monkeypatch.setattr("wid.storage.os.replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        write_text(tmp_path / "other.json", "x")
    assert names(tmp_path) == ["data.json"]
