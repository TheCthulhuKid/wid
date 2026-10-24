# WiD Dice Roller

A terminal dice roller for **We're in Danger**, using Textual and model-owned Pydantic rules.

## Install and run

Requires Python 3.13+. Install [uv](https://docs.astral.sh/uv/), then install from
this directory:

```sh
uv tool install .
wid
```

The `wid` command works from any directory. If your shell cannot find it, run
`uv tool update-shell` and restart the shell. To install from elsewhere, replace
`.` with the path to this project. No package-index release is required.

After updating this checkout, exit the running app and rebuild the installed command:

```sh
uv tool install --force --reinstall .
wid
```

The installed command is a separate copy, not the live checkout. `--force` alone can
reuse a cached build; `--reinstall` rebuilds it so new controls and fixes are included.
Add `--offline` when the build requirements and dependencies are already cached.

For development, run from this directory:

```sh
uv sync
uv run wid
```

You can also launch the package with `.venv/bin/python -m wid`.
Run checks with `uv run pytest` (4 parallel workers by default, about 90 seconds;
add `-m "not ui"` for the quick domain tests, or `-n0` to run serially) and
`uv run ruff check .`.

## Project structure

```text
wid/
├── __init__.py         # Lightweight package marker
├── __main__.py         # python -m wid
├── cli.py              # Installed wid command
├── profiles.py         # Genre metadata and attributes
├── rolls.py            # Validated rules, scoring, and resource transitions
├── formatting.py       # Plain-text roll, dice, and resource renderings
├── export.py           # Markdown text of the action history
├── history.py          # Structured action history entries and their text rendering
├── sessions.py         # Versioned JSON snapshots and atomic local storage
├── storage.py          # Atomic file writes shared by saves
├── settings.py         # Remembered preferences in a small JSON file
└── ui/
    ├── __init__.py
    ├── app.py          # Textual application coordination and event handling
    ├── sessions.py     # Save/load handling mixed into the application
    ├── widgets.py      # Character, options, session, and result widgets
    ├── dialogs.py      # Confirmation screens
    ├── outcomes.py     # Hit, miss, and fumble colours that stay readable in any theme
    └── roller.tcss     # Bundled interface styles
packages/huckdeck/      # Separate distribution (own pyproject.toml and tests)
└── huckdeck/           # cli.py, deck.py, ui/{app,dialogs}.py, ui/dealer.tcss
tests/                  # Domain, persistence, headless UI, and launch tests
game.md                 # Supplied rules
```

The UI calls the domain models; game rules remain independent of Textual.
Persistence depends on the models, not the interface. Package initializers do not
import the application.
WiD and HuckDeck are independent sibling packages: neither imports the other.
They are separate distributions in one uv workspace: installing `wid` does not install
`huckdeck`, and vice versa. Only the root `uv.lock` and dev environment are shared.

## Card dealer

Install with `uv tool install ./packages/huckdeck`, then run `huckdeck`; from a checkout,
`uv sync` also installs it for development.
The package also runs with `.venv/bin/python -m huckdeck`.
For development, `uv sync --offline --locked --group dev` refreshes the installed commands
when dependencies are cached. The `wid` command continues to launch the dice roller.

- The shuffled deck contains 52 standard cards plus **four suited jokers**, one per suit.
- Click **Deal** or press **Ctrl+D**. Drawing an **ace or joker** immediately draws
  another card, continuing until a non-ace, non-joker is drawn or the deck is empty.
  Every card in the chain is removed from the deck and shown in the deal status and
  dealt list; the last card becomes the current card. Aces also appear in the separate
  **Dealt aces** tracker. Running out of cards ends the chain without reshuffling.
- The current card uses a bordered face with colored **♥ ♦ ♣ ♠** symbols and text labels;
  no image files, extra dependencies, or terminal image protocol are required.
- Remaining cards are listed by suit in rank order, without revealing the next draw.
  Dealt cards are listed oldest first. An exhausted deck cannot deal again until shuffled.
- Edit each suit's description; it appears beneath cards of that suit.
- **Restore & shuffle** or **Ctrl+S** returns **all 56 cards**, clears the current card,
  dealt list, and ace tracker, and randomizes the deck. Confirm before discarding dealt cards.
  Suit descriptions are retained. Press **D** to change theme when not typing in a field.

Dealer state and suit descriptions last for the current run only; they are independent of
dice-roller saved sessions. Tab/Shift+Tab navigate controls, Enter activates buttons, and
both panels scroll on smaller terminals. Domain tests inject seeded random sources;
run `.venv/bin/python -m pytest packages/huckdeck/tests` for dealer checks.

## Tests

Run the suite offline with `.venv/bin/python -m pytest`, or focus on persistence
with `.venv/bin/python -m pytest tests/test_sessions.py tests/test_session_app.py`.
Interface tests use Textual's headless runner; no interactive terminal is needed.

Shared pytest fixtures live in `tests/conftest.py`. `session_factory` creates a
fresh game with fixed attribute ranks; `saved_session_factory` creates a seeded,
played session for any genre, including its resources and reroll state. Each call
returns independent state. Save tests use pytest's `tmp_path` fixture so they do
not touch actual campaign files.

## Core controls

At startup and after changing genre kit, assign each attribute a rank from 1–3
and press **Start game** beside **Load game**, to the right of the genre kit.
Every profile, including Core WiD, has three attributes
and uses exactly one 1, one 2, and one 3. Core WiD uses **Athleticism, Composure,
and Reasoning**. Assignments stay fixed until changing kits.
Each attribute has its own **Roll** button, available after pressing **Start game**.
The assigned ranks remain visible and locked during play.

In the **Character** tab under the genre row, enter **Name**, **Looks**, and **Nature**
for your character; the attributes and their Roll buttons are in the same tab.
These optional fields can be edited at any time and stay in place when switching kits.
**Save session** saves them alongside the rest of the game; loading restores them.
Loading asks before
discarding unsaved character details, even before starting a game.

Choose fear (0–3), assistance,
and applicable expertise. The pool preview shows `4 - fear + assistance` dice.
Press **Roll** beside the attribute to test; no attribute selection is needed.
**Ctrl+R** repeats the last-used attribute (the first attribute before any roll).
Tab/Shift+Tab navigate controls; Enter activates a focused Roll button; Space toggles checkboxes;
arrow keys and Enter operate selectors. Configuration and results scroll independently.
Shortcuts, active when you are not typing into a text field and listed in the footer:
**D** picks a theme (remembered in `~/.config/wid/settings.json`, or under
`$XDG_CONFIG_HOME`), **C** and **S** open the Character and Session tabs and focus the tab bar (press Tab to
enter the tab, or the arrow keys to switch tabs), **T** and **I** collapse or expand the strain tracker and the items, and
**Ctrl+L** shows the log. **Ctrl+R** repeats the last roll from anywhere, even in a text
field. Tab never stops on a control in a hidden tab or a collapsed section. The last open
tab and whether the strain tracker and the items are collapsed are remembered in the same
settings file; until you change them, a small terminal starts with both sections collapsed.
Hits, misses, and fumbles are coloured; the words are always shown too, so colour is
never the only signal.

Every kit has name fields for **Expertise**, **Appropriate Item**, and **Inappropriate Item**.
After rolling, select an **Apply to die** target and press **+1 value** beside either named item.
Each press adds +1 to that die's value and recalculates its outcome; either item can be
used repeatedly, including on the same die. Appropriate and inappropriate items have
the same bonus; deciding whether their use makes sense is up to the players.
Item actions never roll dice or spend Tech, strain, or Corruption.
Name expertise and press **+1 hit** to add its single hit after rolling, or check
**Expertise** before rolling to include it immediately. It cannot add a second hit
to the same test, even if renamed. The checkbox configures the next roll; the button
modifies the current result. Blank names disable item actions.
Changing draft fear or assistance does not change the active result or
its item targets. A new roll starts fresh bonuses; Oldheart rerolls keep them.

Results show raw faces, bonuses, effective values, textual outcomes, and totals.
The tested attribute and rank appear with the results, without a separate rank label.
The character/configuration panel uses about two-thirds of the terminal width;
roll output uses the remaining third. The genre row (with Start and Load) is always at the
top, followed by the **Character** and **Session** tabs. Ctrl+R repeats the last roll
even while the Session tab hides the Roll buttons. The strain tracker and the
items are collapsible sections; a collapsed strain tracker still shows its total, such as
`Strain 3 / 12`. In a terminal under 30 rows the controls switch to a one-row form so the
attributes and options fit on screen, and in a terminal under 100 columns or 30 rows the
strain tracker and the items start collapsed. 80x24 is supported.
Each attribute occupies a left-aligned compact row, keeping its label, rank, and Roll
button close together. Fear, Assisted, and Expertise are aligned in one row, with a
small fear selector and a single Assisted label. The Expertise description box sits
beside its checkbox and **+1 hit** button; its text is saved with the session.
Results use `1: 4+1=5 hit` (die number: raw + bonus = effective outcome)
to avoid wrapping; the action log retains fully labeled die details.
The action log is hidden by default to leave more room for attributes, dice, and harm.
Click **Show log / Hide log** above the results, or press **Ctrl+L**, to toggle a compact
history panel. Logging continues while hidden; toggling never clears history or results.
Wound/defeat names move below their checkboxes on narrower terminals so they remain editable.
History is append-only within a game; loading a session restores its saved history.
Invalid inputs leave the last result unchanged.

## Strain, wounds, and defeat

Every kit has a character strain tracker in the configuration panel. Each of its three
rows has three strain checkboxes followed by a fourth box: **Wound**, **Wound**,
then **Defeat**. Enter a name beside each wound or defeat, even before marking it.
The heading shows the current number of marked boxes out of 12, including wound
and defeat boxes. Marked strain boxes are green; marked wounds and defeat are red.
All have a highlighted background, border, and bold check indicator; clearing a box
also reduces the displayed total.
Use **Take 1 strain** to fill boxes sequentially: without recovery, points 4 and 8
mark wounds, and point 12 marks Defeat. Heckboy powers automatically add their
strain costs to this same tracker after a successful roll.

Strain boxes can be marked and cleared in any order, with two rules. A **Wound** or
**Defeat** box can only be marked once every box before it is marked. While a wound is
marked, every box before it stays marked, including earlier wounds, so wounds are cleared
latest first and the strain before each is cleared afterwards. Boxes that cannot change are
disabled, and their tooltip says why. Names are kept when boxes are cleared. Automatic
strain fills unchecked boxes after the last marked Wound/Defeat. After Defeat automatic
strain stops filling boxes; further power costs still appear in cumulative roll totals.
Defeat displays **character ended** but does not disable rolls, notes, or saving.

All boxes and names are saved and loaded with the session; a file with a marked wound
and an unmarked box before it is rejected.
Changing kits clears the tracker and names after confirmation if either contains data.
Recovery edits do not change the separate cumulative Heckboy power-cost total.

## Named sessions

After **Start game**, open the **Session** tab under the genre row.
Enter a **Session name** and a **Save / load file path (JSON)**, then press **Save session**.
Paths can be absolute, relative to the launch directory, or start with `~`.
The parent directory must already exist. Choose a different path to create a
separate copy; overwriting an existing file requires confirmation. Changing only
the name renames the session within that file on the next confirmed save.

**Export history** (beside **Save session**) writes the action history to a Markdown file:
a title, the character's name, looks, and nature, then one numbered section per action with
its dice lines in a code block. The dialog suggests the session file's path ending in
`.md`; replacing an existing file asks first, and there is nothing to export before the first
action.

Use **Session notes** (in the **Session** tab) for multiline character or campaign
notes in Markdown: headings,
**bold**, *italics*, lists, and links. Click **Preview** to see formatted notes in the
same space, then **Edit** to return to the source. Links are displayed but do not open
external pages. **Bold** and **Italic** wrap selected text (or insert example text at
the cursor); **Heading** adds a heading prefix to the current or selected lines.
Formatting can be undone in the editor with **Ctrl+Z**. Tab moves out of the editor
to the notes buttons; these can also be reached with Tab/Shift+Tab and activated with Enter.
Notes stay with the named session when switching genre kits and are saved with
**Save session**, not automatically, including while previewing. Saves preserve the
original Markdown text without changing the file format. Loading replaces both the
editor contents and any visible preview.
Existing plain-text notes remain editable as before; Markdown syntax is interpreted
only in the preview. The Edit/Preview view is not saved.

To resume, press **Load game** beside **Start game** near the top of the configuration
panel. Enter the saved JSON file's path in the prompt, then press **Load game** or Enter.
The prompt starts with the current save/load path, if any; Cancel or Escape leaves
the game and path untouched. No initial attribute setup is needed when loading.
Load game remains available during play. Replacing an active game requires a separate
confirmation; canceling leaves it untouched. Saving, session name, and notes remain
in the session section below.

Saves include the session name, character Name/Looks/Nature, notes, genre, fixed attribute
ranks, fear, assistance, expertise,
expertise/item names, last-used attribute, power choice, item target, Tech strength/target,
strain boxes and wound/defeat names, cumulative power strain, Corruption,
current dice/result, selected reroll dice, and full history.
Draft controls are saved separately from the current test: changing fear before
saving does not change the settings of an existing Oldheart reroll.
Loading never rolls dice, charges resources, or replenishes Tech.
Names remain when switching genre kits.

Saving is explicit, not automatic; save again after playing to keep new changes.
Use a nonblank session name (up to 100 characters). Invalid or
unsupported save files and file-access failures are reported without replacing
the current game. Files use versioned, readable JSON; writes go to a
temporary file that is renamed into place, so a failed write does not leave a
partially overwritten save. (On filesystems without hard links, a new save is
still renamed into place but reserves its filename first.) Window layout and the random
generator's internal state are not saved, and the theme lives in the settings file
instead of the session.

## Genre kits

Select a kit to use its attribute labels. Switching kits clears the active test;
nonzero kit resources require confirmation before being discarded.
History remains available across switches. Confirm the new kit's attribute
assignments before rolling or initializing Tech; canceling a switch keeps the old assignments.

- **Heckboy:** choose no power, reliable (+1 die/+1 strain), or erratic
  (+2 dice/+2 strain). One power activation per test; session strain is tracked.
- **Second Contact:** in addition to the named items available in every kit,
  explicitly initialize/replace the one active Tech resource using the saved
  Science + Culture ranks.
  Select a numbered target before rolling: that die receives the current strength,
  then Tech loses one strength. At zero its target is cleared and use is disabled.
  Rolling a different attribute does not refill Tech; replacement is always explicit.
- **Oldheart:** after rolling, check the numbered result dice to reroll and press
  Reroll selected. Repeat as desired: each selected die adds one Corruption.
  Rerolls retain original item bonuses, assistance, rank, and the single expertise
  hit, regardless of subsequent draft edits. Each action gets its own history entry.
- **Ball Season:** core scoring with Propriety, Stoutness, Yearning; no difficulty subsystem.
- **This Isn't Happening:** core scoring with Instincts, Endurance, Charity;
  spending extra hits is handled outside this roller.

Power strain and Corruption show action deltas and cumulative session totals.
Corruption is displayed only for Oldheart and has no added mechanical consequences or limits.
Rerolls replace faces rather than create a new test.
Tech has no separate inventory or automatic replenishment; its current state is
included when saving a session.
