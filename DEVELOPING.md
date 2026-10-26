# Developing wid

Installing from source, running the tests, building releases, and the files the program
writes. For using the program, see [HOWTO.md](HOWTO.md).

## Install from source

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/). From this directory:

```sh
uv tool install .
wid
```

`wid --version` shows the installed version. It comes from the latest git tag: `v0.2.0`
gives `0.2.0`, and commits after a tag give a dev version such as `0.2.1.dev3+gabc1234`
(with a date added while there are uncommitted changes). Nobody edits a version by hand.
If your shell cannot find `wid`, run
`uv tool update-shell` and restart it. The installed command is a separate copy of the
checkout: after updating, rebuild it with `uv tool install --force --reinstall .`
(`--reinstall` avoids a cached build; add `--offline` when everything is cached).

## Develop

```sh
uv sync --locked --group dev
uv run wid                 # or .venv/bin/python -m wid
uv run wid --web           # the browser version (in progress): 127.0.0.1:8765 or a free port
uv run pytest              # 4 workers, about 80 seconds; -m "not ui" for the quick domain tests
uv run pytest --cov        # as CI runs it: fails below 80% coverage of wid/
uv run ruff check .
uv run ruff format --check .
```

Tests run offline and headless (Textual's test runner). They cover the usual path of each
feature, one domain test and, where there is a screen, one app test, rather than every edge
case. UI tests click through `click` and `reveal` in `tests/helpers.py`, which wait until a
widget has settled on screen. Shared fixtures are in
`tests/conftest.py`; save tests use `tmp_path`, and an autouse fixture points
`XDG_CONFIG_HOME` at a temporary directory so no test touches your real settings.

## Release builds

The Windows release is built with PyInstaller, which lives in its own dependency group
(`uv sync --locked --group dev --group release`; a plain `--group dev` sync removes it).
On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File release\build_release.ps1 -Smoke
```

It installs the pinned environment, builds, runs `wid.exe --self-test`, and (with `-Smoke`)
presses real keys in a Windows pseudo console, then writes the zip and its checksum to `dist\`.
Add `-Python 3.13` to choose the interpreter.

GitHub Actions:

- `.github/workflows/ci.yml` runs two jobs on Linux for every push: the tests (8 workers,
  with coverage) and the quality checks (`ruff check` and `ruff format --check`).
- `.github/workflows/release.yml` builds and smoke-tests the Windows zip on every push to
  `main` and uploads it as a build artifact. Pushing a tag such as `v0.2.0` also attaches the
  zip and checksum to a draft GitHub release, which you publish yourself; the zip, `wid.exe
  --version` and the Windows file properties all take their version from that tag. Without a
  tag, the `publish` job is skipped.

To release, tag the commit and push the tag: `git tag v0.2.0 && git push origin v0.2.0`.
Both workflows check out the full history (`fetch-depth: 0`) so the tag is visible to
`hatch-vcs`.

## Project structure

```text
wid/
├── __init__.py         # Lightweight package marker
├── __main__.py         # python -m wid
├── cli.py              # Installed wid command (--version, --help, --self-test, --web)
├── profiles.py         # Genre metadata and attributes
├── rolls.py            # Validated rules, scoring, and resource transitions
├── formatting.py       # Plain-text renderings: dice, pools, statuses, history lines
├── game.py             # One sitting: the state and actions every front end drives
├── export.py           # Markdown text of the action history
├── history.py          # Structured action history entries and their text rendering
├── sessions.py         # Versioned JSON snapshots and atomic local storage
├── storage.py          # Atomic file writes shared by saves
├── selftest.py         # `wid --self-test`: the app checked headless, for release builds
├── settings.py         # Remembered preferences in a small JSON file
└── ui/
    ├── app.py          # Textual front end: shows the game, passes actions to it
    ├── sessions.py     # Save, load, export and new-character dialogs
    ├── widgets.py      # Character, options, session, and result widgets
    ├── dialogs.py      # Confirmation screens
    ├── outcomes.py     # Hit, miss, and fumble colours that stay readable in any theme
    └── roller.tcss     # Bundled interface styles
└── web/
    ├── server.py       # `wid --web`: listens on 127.0.0.1 only, opens the browser with a token
    ├── app.py          # FastAPI app: the page, POST /actions/<name>, and the safety checks
    ├── forms.py        # The posted sheet fields copied into the game, and the action table
    └── templates/      # Jinja2 page and sheet (the full sheet arrives in PLAN.md step 4)
.github/workflows/      # ci.yml: tests, ruff; release.yml: Windows build, draft release
release/                # PyInstaller spec, Windows build script, smoke test, icon
tests/                  # Domain, persistence, headless UI, and launch tests
HOWTO.md                # How to use the program (for players)
README.md               # Short overview for players, linking to the how-to
```

Front ends call `Game` (`wid/game.py`), which owns the session, history, roll options,
character, notes and file path, records history and words the feedback; game rules stay in
the domain models, independent of Textual. The terminal app copies what the player typed into
the game before each action (`collect`), then redraws from it (`refresh_sheet`), so a second
front end only needs the same two steps; the browser version does them per request (each action
posts the whole sheet, `collect` copies it in, the action runs, the sheet comes back). Every web
request must come from `127.0.0.1` or `localhost`, carry the per-launch token cookie, and, for
actions, htmx's `HX-Request` header (see `wid/web/app.py` for why each check is needed).
Persistence depends on the models, not the interface.
Package initializers do not import the application.

## Files the program writes

**Session files** (JSON, chosen by the player). **Save session** is explicit, never automatic.
A file holds the session name, character details, notes, genre, attribute ranks, the roll
options, item and expertise names, the Heckboy power names and the power chosen for the next
roll, the Tech slots and their names, the Oldheart manifestations, the Ball Season Standing, the This Isn't Happening Resources (pool, waiting die, crafted item), the strain boxes and their names, cumulative
power strain, Corruption, the current dice and result, selected reroll dice, and the full
history. Loading never rolls dice, charges resources or refills Tech. Window layout, the
Edit/Preview choice and the random generator's state are not saved, and the theme lives in the
settings file instead.

- The format is versioned (`version: 1`); files from an unknown version, a marked wound with an
  unmarked box before it, or invalid values are rejected without replacing the current game.
- A save goes to a temporary file that is renamed into place, so a failed write never leaves a
  half-written save. A new save will not overwrite an existing file without confirmation; on
  filesystems without hard links the name is reserved first.

**Settings** (JSON): the theme, the open tab, and whether the strain tracker and items are
collapsed. They live in `~/.config/wid/settings.json`, `%APPDATA%\wid\settings.json` on
Windows, or under `$XDG_CONFIG_HOME` when it is set. A missing or invalid file means defaults.

**Exported history** is a Markdown file: a title, the character's name, looks and nature, then
one numbered section per action with its dice lines in a code block.
