# Changelog

What changed in each release of wid, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow the release tags.

## [Unreleased]

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

[Unreleased]: https://github.com/TheCthulhuKid/wid/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/TheCthulhuKid/wid/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/TheCthulhuKid/wid/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/TheCthulhuKid/wid/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/TheCthulhuKid/wid/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/TheCthulhuKid/wid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/TheCthulhuKid/wid/releases/tag/v0.1.0
