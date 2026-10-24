import os
import stat
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile


def write_text(path: Path, text: str, *, overwrite: bool = False) -> None:
    """Write ``text`` to ``path`` through a temporary file in the same directory.

    With ``overwrite=False`` an existing file raises ``FileExistsError`` and is left alone.
    """
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(text)
            output.flush()
            mode = _target_mode(path)
            # Some filesystems (e.g. FAT) cannot set permissions; the write still works.
            with suppress(OSError):
                os.chmod(temporary, mode)
            os.fsync(output.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            _publish_new(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _target_mode(path: Path) -> int:
    """Keep an existing file's permissions; otherwise honour the umask."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def _publish_new(temporary: Path, path: Path) -> None:
    """Move a finished file into place without replacing an existing one."""
    try:
        os.link(temporary, path)
    except FileExistsError:
        raise
    except OSError:
        # No hard links (e.g. FAT/exFAT): reserve the name exclusively, then
        # rename over the empty reservation so the path never holds a partial file.
        path.open("xb").close()
        try:
            os.replace(temporary, path)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
