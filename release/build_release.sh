#!/usr/bin/env bash
# Builds the Linux or macOS release: wid-<version>-<system>-<arch>.tar.gz and a matching
# .sha256 in dist/.
#
# Needs uv (https://docs.astral.sh/uv/). The environment comes from uv.lock, so the build uses
# the same pinned versions as development. Run from anywhere:
#
#     release/build_release.sh [python-version]
#
# The program is tested before it is packaged: `wid --self-test` must pass. A tar keeps the
# executable bit, which a zip made by Python's zipfile would lose.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

# The ${a[@]+...} form keeps an empty array working under set -u in the bash 3.2 macOS ships.
python_args=()
if [[ $# -gt 0 ]]; then python_args=(--python "$1"); fi

echo "==> Installing the pinned build environment"
uv sync --locked --no-dev --group release --no-editable ${python_args[@]+"${python_args[@]}"}

# The installed version, which hatch-vcs took from the git tag (a dev version between tags).
version="$(uv run --no-sync ${python_args[@]+"${python_args[@]}"} python -c \
    "from importlib.metadata import version; print(version('wid'))")"
case "$(uname -s)" in
    Darwin) system=macos ;;
    *) system=linux ;;
esac
arch="$(uname -m)"
if [[ "$arch" == aarch64 ]]; then arch=arm64; fi
name="wid-$version-$system-$arch"
echo "==> Building $name"

rm -rf build dist/wid "dist/$name" "dist/$name.tar.gz" "dist/$name.tar.gz.sha256"
uv run --no-sync ${python_args[@]+"${python_args[@]}"} pyinstaller release/wid.spec \
    --noconfirm --log-level WARN

program="$root/dist/wid"
if [[ ! -x "$program" ]]; then echo "PyInstaller did not produce $program" >&2; exit 1; fi

echo "==> Checking the built program"
reported="$("$program" --version)"
if [[ "$reported" != "wid $version" ]]; then
    echo "Built program reports '$reported', expected 'wid $version'" >&2
    exit 1
fi
"$program" --self-test

echo "==> Packaging"
stage="$root/dist/$name"
mkdir "$stage"
cp "$program" "$stage/wid"
cp release/README-unix.txt "$stage/README.txt"
cp HOWTO.md "$stage/HOWTO.md"
tar -czf "dist/$name.tar.gz" -C dist "$name"
rm -rf "$stage"

cd dist
if command -v sha256sum > /dev/null; then
    sha256sum "$name.tar.gz" > "$name.tar.gz.sha256"
else
    shasum -a 256 "$name.tar.gz" > "$name.tar.gz.sha256"
fi

echo
echo "Done: $root/dist/$name.tar.gz"
echo "SHA-256: $(cut -d ' ' -f 1 "$name.tar.gz.sha256")"
