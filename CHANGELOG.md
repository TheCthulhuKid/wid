# Changelog

What changed in each release of wid, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow the release tags.

## [Unreleased]

## [0.6.0] - 2026-11-18

### Added

- Heckboy: **Second Wind** beside **Take 1 wound** clears 2 strain once per character. Wounds,
  and strain before a marked wound, stay marked.
- **Recover** after a Danger: choose its difficulty and Heckboy clears the strain its kit gives
  back, or This Isn't Happening gains the Resources.
- This Isn't Happening: **Build barricade** and **Strengthen barricade** spend Resources and note
  the strength, and **Sacrifice** beside an item gives it up for 3 Resources.
- Ball Season: **Target standing** before a roll says how many more hits the test needs to pass,
  one per tier of standing between you and the target; in the GM mode, **PCs of another
  standing** adds their strain to a task.
- In the GM mode, **Acting Danger** chooses whose loadout the activations roll on once a scene
  has two or more Dangers, and the loadout table names its Danger.
- In the GM mode, the **Scenario** tab holds the scenario sheet: its title, pitch and cast, the
  four lists and the incitement table, and up to six Dangers with descriptions and notes. It is
  saved with the GM's game. **A** opens it in the terminal; in the browser it is a section below
  the scene.
- In the GM mode, **Import scenario** and **Export scenario** on the Scenario tab read and write
  a scenario sheet in Markdown, named in **Scenario file**. A file of several scenarios asks
  which one, and an export writes wid's hits, threshold and loadout table for each Danger. In
  the browser, **Upload a scenario** and **Download scenario** do the same.
- In the GM mode, **Start scene** on the Scene tab runs a scenario Danger, with its description
  and notes under the loadout table; **End scene** and **They're dead. They're all dead!** write
  the scene and its **Scene notes** to the history, and **Roll on** rolls on a scenario list or
  the incitement table. After each scene, **Scenario Danger** offers the next one.
- In the GM mode, **Danger reference** on the Scene tab shows what each class and difficulty
  gives a Danger, for the kit and the number of PCs.
- Oldheart: **Avoid strain** beside **Gain Corruption** takes the Corruption for strain avoided
  on a task and says so in the history.

### Changed

- Each genre kit has its own highlight colour in the default "danger" theme and in the browser:
  green for Ball Season, orange for Heckboy, plum for Oldheart, brown for This Isn't Happening
  and blue for Second Contact. Core WiD stays red, and fumbles stay red in every kit.
- In the GM mode, an activation names the Danger it rolled for, such as "Zeus (Mega Titan)
  activates (4, 2, 5): Kill — …".
- **Undo** goes back up to 10 changes, not 50, in both modes.
- The how-to's **Undo** paragraph is shorter.
- In the GM mode, the Competent difficulty is now **Heavy**, as the game's creator renamed it.
  A GM save from 0.5.0 opens with its Competent Dangers as Heavy.
- GM saves have a new format. Older GM saves still open, but a GM save from this version needs
  this version of wid or later.

### Fixed

- In the browser, wid now asks whether to **Restore** a game it closed without saving, as the
  terminal does. Before, the question never showed, and the next change replaced the kept copy.
- In the GM mode, Undo after removing a Danger no longer moves a name you typed since onto
  another Danger.
- A GM save from a newer wid now says to update wid, instead of "Input should be 1".
- What you type, such as notes and names, reaches the recovery copy a few seconds after you
  stop typing, in the terminal and the browser. Before, it waited for the next button or box.
- A save file with no version is refused, saying wid did not save it. Before, it was read as
  the current version.
- In the browser, **Download save** and **Download history** include what you typed just
  before, and a download that is refused says why on the page. Before, the file left out text
  typed since the last button or box, and a refused download only failed.
- In the GM mode, **Raise threshold** waits for a Danger, as **Commit hits** does. Before, it
  raised the threshold of an empty scene, and the first Danger added started with that raise.
- In the terminal, settings that cannot be saved are reported as other file errors are, such as
  "Could not save settings: Permission denied: …/settings.json", without Python's error number.

## [0.5.0] - 2026-10-28

### Added

- **GM mode**: `wid --gm` runs the Game Master's screen, and `wid --web --gm` the same page in
  the browser. Choose the **PCs**, a Danger's **Class** and **Difficulty**, and wid gives its
  threshold, hits to pass and loadout; **Activate Danger** rolls its ability, target and
  defending attribute in the current kit's words, and the scene tracks hits committed, a raised
  threshold and Dangers that fight each other. GM saves are their own kind of file and open in
  GM mode by themselves.
- **Save first** on the question asked when changing kit with unsaved changes, in the terminal
  and the browser.
- **Task strain** in the GM mode: choose a task's complexity and wid logs the strain total the
  PCs share.
- The kits' scene trackers in the GM mode: a Danger's **Standing** in Ball Season, the
  **Barricade** in This Isn't Happening, and the **Revelations** track in Oldheart, each saved
  with the scene and undoable.

### Changed

- `wid --self-test` also starts the GM screen, activates a Danger and serves the GM page.
- **Load game** is now **Load session**, the Session tab's path box is **Session file (JSON)**,
  and the name box says "Name this session": a session is what you save and load.
- **Gain Corruption** and **Crafted Item** are written as the rules write them.
- The browser uses the terminal's words: the totals read "Hits: 1 (dice 1, expertise 0)", a Tech
  slot reads "Tech 1, strength 3", and the hints before a game starts and before a roll match.
- Every message under the controls ends with a full stop, and "cancelled" is spelled the British
  way.
- Rolling before **Start game** says "Set the ranks and press Start game first."
- The new-character question says that the session name stays too.
- The Resources buttons are labelled "Take 1 from Resources" and "Add 1 to Resources".
- A succumbed Oldheart character's sheet line names the manifestations before "Succumbed:".
- The command palette (Ctrl+P) offers the game's actions only when no question is open.
- The how-to lists everything Undo takes back and more of the browser's differences.

### Fixed

- Undo keeps the names you typed after the change it takes back: items, expertise, powers,
  manifestations, Tech pieces and strain rows.
- Undoing anything but a roll no longer resets Assisted, Expertise or the power you chose since.
- Undo's history entries read "Undid the last bonus: ..." instead of "Undid the last bonus.: ...".
- In the terminal, the Export history and Spend 6 Resources boxes sit in the middle of the
  screen like the other questions, and the Spend box fits an 80×24 terminal.
- In the browser, a save picked to upload while wid is busy is reported instead of dropped, and
  cancelling a question no longer sends its upload along with every later action.
- A download or export no longer suggests a file called `..`.
- A session name over 100 characters no longer stops the recovery copy.
- A power name of only spaces no longer shows on the exported sheet.
- `wid --web --port abc` says "'abc' is not a port (use 0 to 65535)".

## [0.4.2] - 2026-10-27

### Added

- A recovery copy: wid keeps unsaved changes as you play and offers them back the next time it
  starts.
- Open a save straight away by naming it: `wid game.json`, or **Open with** on Windows.
- **Undo** takes back any change to the sheet, up to 50 changes.
- **Download save** and **Upload a save** in the browser.
- **Copy result** copies the dice as text, for pasting into a chat.
- The command palette (Ctrl+P) lists the game's main actions.
- **Export history** writes the sheet and the notes too.
- Dice statistics in the history and at the end of the export.

### Changed

- The browser's **Colours** switch can go back to your system's light or dark setting (Auto).

## [0.4.1] - 2026-10-27

### Fixed

- The Windows release is built again: its check before publishing answers the quit question.

## [0.4.0] - 2026-10-27

### Added

- Linux and macOS releases alongside Windows.
- wid asks before quitting with unsaved changes.
- Strain, Standing and Resources changes are noted in the history.
- A light and dark switch in the browser sheet.
- The readme explains a double-click shortcut for the browser version on Windows.

### Fixed

- Refused actions show a readable message.
- Oldheart has a reroll box for every die in its largest pool.
- The browser sheet copes with quotes in names, double clicks and a stopped wid.
- A save from a newer wid says so, and a save with an unreadable version is refused.
- Two browser games can run at once.
- The browser keeps the cursor where it was, Ctrl+R does nothing behind a question, and a change
  made while wid is busy is reported.
- A folder is refused as a file path, and a failed write names the file.
- Checks after succumbing are worded as such, and pressing Ctrl+Q twice asks once.

## [0.3.0] - 2026-10-26

### Added

- `wid --web` plays the same game in a browser on this computer: a character sheet with save,
  load and export, asking first as the terminal does.
- The self-test covers the browser version.

### Fixed

- A typed export path is kept, and typing that is not saved yet counts as unsaved.

## [0.2.0] - 2026-10-26

### Added

- Oldheart: Corruption, manifestation checks and their effect on Depravity and Hospitality.
- This Isn't Happening: Resources, the crafted item and **Roll 1d6**.
- Ball Season: the Standing track.
- Second Contact: Tech as named pieces, one slot per Muscle rank, with **Sacrifice**.
- Heckboy: two named powers.
- **New character**, and changing kit starts a new game.
- **Take 1 wound**.
- The Danger theme.

### Changed

- Each item can be used on one die per roll, and the power is cleared after a roll.
- Fear is now called Scared.
- Second Contact hides the items.
- The notes toolbar sits above the editor, and **Take 1 strain** above the boxes.
- The action buttons are coloured.
- The readme starts with the how-to.

### Removed

- The marked-strain line under the strain tracker's title.

## [0.1.0] - 2026-10-25

### Added

- A terminal dice roller for We're in Danger: choose a genre kit, rank the attributes and roll
  tests with the options, expertise and items.
- A strain tracker with wounds and Defeat: a wound needs the strain before it, and locks it.
- Save and load sessions, keep notes, and export the history as Markdown.
- Character and Session tabs, sections that fold, and a layout that fits the terminal and is
  remembered.
- Themes, remembered with your settings.
- A Windows program that needs no Python, and installing with uv.

[Unreleased]: https://github.com/TheCthulhuKid/wid/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/TheCthulhuKid/wid/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/TheCthulhuKid/wid/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/TheCthulhuKid/wid/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/TheCthulhuKid/wid/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/TheCthulhuKid/wid/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/TheCthulhuKid/wid/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/TheCthulhuKid/wid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/TheCthulhuKid/wid/releases/tag/v0.1.0
