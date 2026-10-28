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
If your shell cannot find `wid`, run `uv tool update-shell` and restart it. The installed
command is a separate copy of the checkout: after updating, rebuild it with
`uv tool install --force --reinstall .` (`--reinstall` avoids a cached build; add `--offline`
when everything is cached).

## Develop

```sh
uv sync --locked --group dev
uv run wid                 # or .venv/bin/python -m wid
uv run wid --web           # the browser version: 127.0.0.1:8765 or a free port
uv run pytest              # a worker per core: about 60 s on 16 cores, 5 s with -m "not ui"
uv run pytest --cov        # as CI runs it: fails below 80% coverage of wid/
uv run ruff check .
uv run ruff format --check .
```

Tests run offline and headless (Textual's test runner). They cover the usual path of each
feature, one domain test and, where there is a screen, one app test, rather than every edge
case. UI tests start the app with `run_app` and click through `click` and `reveal` in
`tests/helpers.py`, which wait until a widget has settled on screen. Every test that starts the
app carries the `ui` marker (`pytestmark` for a whole module, `@pytest.mark.ui` otherwise), so
mark a new one too. Shared helpers live in `tests/helpers.py`, never in another test module.
Shared fixtures are in `tests/conftest.py`; save tests use `tmp_path`, and an autouse fixture
points `XDG_CONFIG_HOME` at a temporary directory so no test touches your real settings.

## Release builds

The releases are built with PyInstaller, which lives in its own dependency group
(`uv sync --locked --group dev --group release`; a plain `--group dev` sync removes it).
Each system builds its own release; PyInstaller cannot cross-compile. On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File release\build_release.ps1 -Smoke
```

It installs the pinned environment, builds, runs `wid.exe --self-test` (which also serves the
browser version once through uvicorn, proving its by-name imports, templates and static files
were bundled), and (with `-Smoke`)
presses real keys in a Windows pseudo console, then writes the zip and its checksum to `dist\`.
Add `-Python 3.13` to choose the interpreter.

On Linux or macOS:

```sh
release/build_release.sh [3.13]
```

It builds a single-file program, runs `wid --version` and `wid --self-test`, then writes
`wid-<version>-<linux|macos>-<arch>.tar.gz` (the program, `README-unix.txt` as `README.txt`,
and `HOWTO.md`) and its checksum to `dist/`. A tar keeps the executable bit. There is no
pseudo-console smoke test on these systems. Like the Windows script, it syncs the project
environment without the dev group, so run `uv sync --locked --group dev` afterwards, or set
`UV_PROJECT_ENVIRONMENT` to build in a separate environment.

GitHub Actions:

- `.github/workflows/ci.yml` runs two jobs on Linux for every push: the tests (8 workers,
  with coverage, then `wid --self-test`) and the quality checks (`ruff check` and
  `ruff format --check`).
- `.github/workflows/release.yml` builds and smoke-tests the Windows zip, and builds and
  self-tests the Linux x86_64 (on Ubuntu 22.04, for the widest glibc support) and macOS arm64
  archives, on every pull request and every push to `main`, uploading each as a build artifact.
  Pushing a tag such as `v0.2.0` also attaches every archive and checksum to a draft GitHub
  release, which you publish yourself; the file names, `wid --version` and the Windows file
  properties all take their version from that tag. Without a tag, the `publish` job is skipped.

A change a player would notice adds a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md),
in the same change. To release, rename **Unreleased** to the version and date (such as
`## [0.5.0] - 2026-11-02`), add an empty **Unreleased** above it and the compare links at the
end, then tag that commit and push the tag: `git tag v0.5.0 && git push origin v0.5.0`. The
`publish` job takes the draft release's notes from that version's section
(`release/changelog_notes.py`) and stops if there is none. Both workflows check out the full
history (`fetch-depth: 0`) so the tag is visible to `hatch-vcs`.

## Project structure

```text
wid/
├── __init__.py         # Lightweight package marker
├── __main__.py         # python -m wid
├── cli.py              # wid command: a save, --web, --port, --no-browser, --self-test, --version
├── profiles.py         # Genre metadata and attributes
├── rolls.py            # Validated rules, scoring, and resource transitions
├── dangers.py          # The GM's Dangers: loadouts, a scene's threshold and activation
├── formatting.py       # Plain-text renderings: dice, pools, statuses, history lines
├── game.py             # One sitting: BaseGame (history, save, undo, recovery) and the player's Game
├── gm.py               # The GM's game: the kit, the scene and an action for each control
├── export.py           # Markdown export: the sheet, the notes and the action history
├── history.py          # Structured action history entries, their text, and dice statistics
├── sessions.py         # The versioned save format and the session file path rules
├── storage.py          # Atomic file writes for saves, exports and settings
├── selftest.py         # `wid --self-test`: the app checked headless, for release builds
├── settings.py         # Remembered preferences in a small JSON file
├── ui/
│   ├── app.py          # Textual front end: shows the game, passes actions to it
│   ├── sessions.py     # Save, load, export, new-character, quit and recovery dialogs
│   ├── widgets.py      # Character, options, session, and result widgets
│   ├── dialogs.py      # Confirmation screens
│   ├── outcomes.py     # Hit, miss, and fumble colours that stay readable in any theme
│   ├── themes.py       # The default danger theme: cream paper, lavender fields, red highlights
│   └── roller.tcss     # Bundled interface styles
└── web/
    ├── server.py       # `wid --web`: listens on 127.0.0.1 only, opens the browser with a token
    ├── app.py          # FastAPI app: the page, POST /actions/<name>, downloads, safety checks
    ├── forms.py        # The posted sheet fields copied into the game, and the action table
    ├── view.py         # Colours (light and dark), the notes preview, the template context
    ├── templates/      # Jinja2 page and sheet: one form, each button posts to its action
    └── static/         # sheet.css, and sheet.js: posts the form and swaps the reply in
.github/workflows/      # ci.yml: tests, ruff; release.yml: builds for each system, draft release
release/                # PyInstaller spec, build scripts, readmes, smoke test, icon, release notes
tests/                  # Domain, persistence, headless UI, and launch tests
HOWTO.md                # How to use the program (for players)
README.md               # Short overview for players, linking to the how-to
CHANGELOG.md            # What changed in each release, for players
```

Front ends call `Game` (`wid/game.py`), which owns the session, history, roll options,
character, notes and file path, records history and words the feedback; game rules stay in
the domain models, independent of Textual. What is not the character sheet (the history, the
session name, notes and file path, Undo, saving, loading, exporting and the recovery copy) is
`BaseGame`, so another mode of play only supplies its own state and save model. The terminal app copies what the player typed into
the game before each action (`collect`), then redraws from it (`refresh_sheet`), so a second
front end only needs the same two steps; the browser version does them per request (each action
posts the whole sheet, `collect` copies it in, the action runs, the sheet comes back). Every web
request must come from `127.0.0.1` or `localhost`, carry the per-launch token cookie, and, for
actions, the `HX-Request` header that `sheet.js` adds (see `wid/web/app.py` for why each check
is needed). The cookie is named after its token, so two `wid --web` games can run at once in one
browser.
Persistence depends on the models, not the interface.
Package initializers do not import the application.

## Files the program writes

**Session files** (JSON, chosen by the player). **Save session** is explicit, never automatic.
The terminal and the browser version read and write the same files.
A file holds the session name, character details, notes, genre, attribute ranks, the roll
options, item and expertise names, the Heckboy power names and the power chosen for the next
roll, the Tech slots and their names, the Oldheart manifestations, the Ball Season Standing, the
This Isn't Happening Resources (pool, waiting die, crafted item), the strain boxes and their
names, cumulative power strain, Corruption, the current dice and result, the dice selected for a
reroll and the die chosen for an item, and the full history. Loading never rolls dice, charges
resources or refills Tech. Window layout, the Edit/Preview choice, the undo history and the
random generator's state are not saved, and the theme lives in the settings file instead. So
**Undo** has nothing to take back right after a load, until the next change.

- The format is versioned (`version: 2`); files from an unknown version, a marked wound with an
  unmarked box before it, or invalid values are rejected without replacing the current game. A
  file from a newer wid says so and asks the player to update.
- A change to the save format bumps `version` on `SavedSession` and adds one function to
  `UPGRADES` in `wid/sessions.py`, keyed by the old version, that turns an old file's data into
  the new version's. Loading runs the steps in turn, so files of every earlier version still load.
- A save goes to a temporary file that is renamed into place, so a failed write never leaves a
  half-written save. A new save will not overwrite an existing file without confirmation; on
  filesystems without hard links the name is reserved first.

**GM session files** are the same kind of file with `kind: "gm"` and their own `version: 1`
(`GmSave` in `wid/sessions.py`). One holds the session name, the genre kit, the PC count, the
Dangers with their names, classes and difficulties, the hits committed, the raised threshold,
whether the Dangers fight each other, the notes and the history. The last activation is not
saved; the history has it. A player's file has no `kind`, and each mode refuses the other's
file with a message naming the flag to start wid with. A change to the GM format bumps
`GmSave.version` and gets its own upgrade table, separate from the player's.

**Recovery copy** (JSON): `recovery.json` beside the settings, and `gm-recovery.json` for the
GM mode, so a GM and a player on one computer never overwrite each other's. While the game has
unsaved changes and has started, `BaseGame.keep_recovery` writes it after every change (the terminal from
`refresh_sheet`, the browser after each action), in the save format with the typed session name
and file path beside it. It goes once nothing is unsaved (a save, a load, a new kit) or when
the player quits after agreeing to lose the changes. On start, an untouched game offers it back;
**Start fresh** leaves it until the new game writes over it. It is the most recent game, so two
games running at once take turns in it. A write that fails is reported once and play goes on.

**Settings** (JSON): the theme, the open tab, and whether the strain tracker and items are
collapsed. They live in `~/.config/wid/settings.json`, `%APPDATA%\wid\settings.json` on
Windows, or under `$XDG_CONFIG_HOME` when it is set. A missing or invalid file means defaults.

**Exported history** is a Markdown file: a title, a line with the character's name, looks and
nature, a Sheet section summing up the sheet, the Notes as written, one numbered section per
action with its dice lines in a code block, then the dice Statistics.
