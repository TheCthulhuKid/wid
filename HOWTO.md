# How to use wid

wid is a dice roller and tracker for **We're in Danger**.

## Start

1. Choose a **Genre kit** (top left in the terminal, top right in the browser). Core WiD is the
   default.
2. Give each attribute a different rank (1, 2 or 3) in the **Character** tab.
3. Press **Start game**. The ranks are locked until you change kit or start a new character.
4. Press **Roll** beside an attribute. The result appears on the right.

**Load session** (next to Start game) opens a saved session instead. **Ctrl+Q** quits, asking
first if anything is unsaved.

## Rolling

Set the options under the attributes, then press **Roll**:

- **Scared**: pick 0 to 3.
- **Assisted**: tick it when the roll is assisted.
- **Expertise**: tick it to include your expertise in the next roll.

**Assisted**, **Expertise** and a Heckboy power apply to one roll: they untick themselves
afterwards, so tick them again when they apply to the next one. **Scared** stays as you set it.

The line under the options shows the size of the pool (for example `Pool: 4d6`). The result
lists every die as *hit*, *miss* or *fumble* (green, yellow, red) with the totals below.

**Ctrl+R** rolls again with the last attribute you used, from anywhere in the program.

**Roll 1d6** (beside **Show log**) rolls a single die outside a test, for anything the game asks
you to roll, and writes the result to the history.

**Show log** (in the browser, the History list) shows the history, headed by how the dice have
fallen so far: the number of tests, their hits, misses and fumbles as first rolled, and how often
each pool size came up. Rerolls and bonuses are left out, so no die counts twice.

**Copy result** (under the result) copies the attribute, each die and the totals as plain text,
ready to paste into a chat. In the terminal it goes through the terminal's clipboard, which most
terminals pass on (macOS Terminal does not).

**Undo** (under the result) takes back the last change to the sheet: a roll, a reroll, an item,
expertise or Tech bonus, New scenario, a sacrificed piece of Tech, strain, Standing, Resources,
a lost crafted item, Corruption or a manifestation. Press it again for the one before, up to 50
changes. The history keeps what happened and notes each undo.
An undone roll is not rolled back into the dice: rolling again gives new numbers. Names typed
since the change stay, and only undoing a roll brings back the attribute, Assisted, Expertise
and power it cleared. Loading a game, starting a new character or changing the kit starts with
nothing to undo.

## Items and expertise

Type a name for each item under **Items** (**Appropriate Item** and **Inappropriate Item**).
Second Contact has no items: Tech replaces them, so the section is called **Tech** there and holds
your Tech slots instead (below). **Apply to die** works the same way for Tech.
After a roll:

1. Choose a die in **Apply to die**.
2. Press **+1 value** beside the item you are using.

Each item adds +1 to a single die, once per roll; its button greys out until your next roll. Use
the other item on the same die or another. **Undo** takes back the last bonus and frees it
again. For expertise, name it and press **+1 hit** (or tick **Expertise** before rolling). Buttons
stay greyed out until the name is filled in and there is a roll to change.

## Genre kits

Every kit has the same screen. Each adds at most one thing:

| Kit | Attributes | Extra control |
|---|---|---|
| **Core WiD** | Athleticism, Composure, Reasoning | None |
| **Heckboy** | Aberrance, Ferocity, Savvy | Two powers (below) |
| **Second Contact** | Science, Culture, Muscle | **Tech** slots instead of **Items** (below) |
| **Oldheart** | Depravity, Hospitality, Fitness | Rerolls, Corruption and manifestations (below) |
| **Ball Season** | Propriety, Stoutness, Yearning | A **Standing** track (below) |
| **This Isn't Happening** | Instincts, Endurance, Charity | **Resources**, a crafted item (below) |

**Powers (Heckboy).** Every Heckboy has a **Reliable power** (+1 die, +1 strain) and an
**Erratic power** (+2 dice, +2 strain). Type each power's name in its box. Tick **Use** beside one
before rolling to use it: the pool grows and the strain is added to the tracker for you. Only one
power can be used per roll, and **Use** unticks itself after the roll.

**Tech (Second Contact).** You get one Tech slot for each rank of Muscle as soon as the game starts.
A slot stays empty until you use it, and each one starts at Science + Culture. Tech is used after
rolling, like an item:

1. Type a name in an empty slot (or use a slot you named before).
2. Choose a die in **Apply to die** and press **Use** on that piece.

The die gets the piece's strength, and the piece loses 1 for next time. You can use several pieces
on one test, each once. At 0 a piece is depleted and its buttons grey out. **Undo** takes a use
back and returns the strength. To stop a Danger's extermination, press **Sacrifice** on a named
piece that still works: its strength drops to 0 and the history notes it. At the start of each
scenario, press **New scenario** to empty every slot again. **Undo** takes either back too.

**Standing (Ball Season).** A five-dot track: **Esteemed** on the left, **Scandalous** on the
right, and **Reputable** for the three dots in between. You start on the centre dot. Click a dot,
or click the track and press ← and →, to move. Standing never changes your dice; the GM uses it
to set how many hits a test needs.

**Corruption (Oldheart).** Tick dice in the result, then press **Reroll selected**: each rerolled
die costs 1 Corruption. For Corruption from anything else, such as a Danger or strain you chose
to avoid, choose how much in the box beside **Gain Corruption** and press it. Corruption never
goes down during a scenario. Every gain makes a manifestation check for you: one die per point
just gained, and a total at or under your new Corruption means a manifestation. The dice and the
outcome go to the history. Name each manifestation in its box. Use **Add manifestation** for one
from elsewhere (such as delivering an undesirable quarry) and **Remove manifestation** to undo a
mistake. Each manifestation adds 1d6 to Depravity tests and takes 1d6 from Hospitality tests, as
the pool line shows; a test always rolls at least 1d6. At the third manifestation the character
succumbs and becomes a Brute Danger for the GM.

**Resources (This Isn't Happening).** Your pool starts at your Charity rank when the game starts
and stays between 1 and 6. Press **−** or **+** when a task taxes it, a Danger depletes it, or
you spend extra hits on it (after a roll with extra hits, the result panel reminds you). At 6,
press **Spend 6 Resources** and choose one effect; the pool then resets to your Charity rank:

- **+1d6 on the next test** (to confront a Danger or defend against it): the pool line shows the
  extra die until your next roll.
- **Automatically pass** an obstacle that does not involve a Danger: noted in the history.
- **Craft an item**: unlocks the **Crafted Item** line under **Items**, your third item. Name it
  and use it like the others. Press **Lose** if it is lost; that frees the slot to craft again.
- **Recover 1d6 strain**: rolls the die and unmarks that much of your newest strain. Wounds,
  and strain before a marked wound, stay marked.

**Changing kit.** A kit lasts the whole game, so picking another kit in **Genre kit** starts a
new game: the character, names, strain, history, notes, session name and file path are all
cleared. You are asked first if there is anything unsaved. Set the ranks and press
**Start game**.

## Strain tracker

Three rows of boxes: strain, strain, strain, then a wound (the last row ends in Defeat).

- **Take 1 strain** fills the next box. **Take 1 wound** fills every box up to and including
  the next wound (Defeat after the second). You can also click boxes yourself.
- A wound can only be ticked after every box before it is ticked.
- While a wound is ticked, the boxes before it stay ticked. Clear the latest wound first.
- Boxes that cannot change are greyed out; hover over one to see why.
- Type a name beside each wound.

The title counts what is marked (`Strain tracker: 3 strain, 1 wound`), even when the tracker is
folded away. A wound is not counted as strain.

## Character, notes and saving

**Character** tab: your name, looks and nature, plus the attributes.

**Session** tab: the session name, your notes, and the file path.

- Notes accept Markdown. **Preview** shows it formatted and **Edit** takes you back.
- **Save session**: enter a session name and a file path, then press the button. You are asked
  before an existing file is replaced.
- **Load session**: press it and a box asks for the path; it starts with the one from the Session
  tab. You are asked first if you would lose anything unsaved.
- **Export history**: writes a Markdown file you can read or share: your character, a summary of
  the sheet (ranks, strain, named items and powers, and your kit's Tech, Corruption, Standing or
  Resources), your notes, then all the rolls and every change to strain, Standing and Resources,
  and the dice statistics. The suggested name is your save file's name ending in `.md`.
- **New character**: clears the sheet for a new character in the same kit (after a character
  dies, for example): name, looks, nature, ranks, item and expertise names, strain, Scared and the
  current roll. The history, notes, session name and file path stay. You are asked first if
  there is anything to lose. Set the ranks again and press **Start game**.

A save includes everything on screen: kit, ranks, options, items, Tech, strain, Corruption,
notes, character details and the history.

To open a save as wid starts, name it: `wid game.json`, or `wid --web game.json` for the
browser. On Windows you can also right-click a save, choose **Open with** and pick `wid.exe`.
If the file cannot be opened, wid starts an empty game and says why.

While a game has unsaved changes, wid also keeps a recovery copy of it beside its settings. If
wid closes without a save (a crash, or a closed window), the next start asks whether to
**Restore** that game or **Start fresh** (**Keep the opened game** if you named a save to open).
A restored game still needs saving. **Start fresh**
keeps the copy until the new game has something to lose, and quitting with Ctrl+Q after saying
you will lose your changes removes it. Two games running at once share the one copy, so it
holds whichever changed last.

## GM mode

Running the game rather than playing a character? Start wid with `wid --gm` (from a release
download, `.\wid.exe --gm` on Windows or `./wid --gm` on Linux and macOS). The screen has no
character sheet: the **Scene** tab on the left holds the Dangers, and the right side rolls for
them. Opening a GM save (`wid scene.json`) starts this mode by itself.

**Scene** tab:

- **PCs**: how many player characters are in the scene (1 to 8). The Dangers' thresholds follow.
- To add a Danger, type a name (optional), choose its **Class** and **Difficulty** and press
  **Add Danger**. The four base classes are always offered; each kit adds its own class.
  Each Danger is listed with its threshold and the hits a PC needs to pass; type its name in
  the box beneath, or press **Remove** to take it out of the scene. A scene holds up to four.
- The line under the Dangers is the scene: the combined threshold, what has been committed
  and the hits to pass of the strongest Danger.
- Choose an **Amount**, then press **Commit hits** to progress the threshold, or press
  **Raise threshold** when a Danger's ability raises it. Committed hits never go past the
  threshold.
- Tick **Dangers fight each other** when the Dangers are hostile to one another; at the end
  of a round, **Dangers clash** rolls 1d6 and commits it.

On the right, **Activate Danger** (or **Ctrl+R**) rolls 3d6 and shows which ability the Danger
uses, who it targets and the attribute the targets defend with, in the words of the current
kit. The table below it is the loadout of the strongest Danger, one row per die. **Roll 1d6**
rolls a single die, and **Undo** takes back the last change to the scene (not an activation).

The **Session** tab, **Save session**, **Load session**, **Export history**, the history log,
the theme and the command palette work as in the player's mode. A GM save is its own kind of
file: the player's mode refuses it, and this mode refuses a player's save, each saying which
way to start wid. The recovery copy is separate too, so a GM and a player on one computer
never overwrite each other's.

**Changing kit** asks what to do with the scene when there is anything unsaved: **Save first**
saves and then changes kit, **Keep scene** keeps the Dangers, history and notes (a Danger of a
class the new kit lacks is dropped and named; **Undo** brings it back), **Start new** clears
everything, and **Cancel** keeps the current kit. The player's mode offers **Save first** too,
beside **Start new game** and **Keep current game**.

Keys: **E** opens the Scene tab and **S** the Session tab; **Ctrl+R** activates the Danger. The
other keys are the ones below, except **C**, **T** and **I**, which belong to the character
sheet.

**In the browser**, `wid --web --gm` serves the GM page instead of the character sheet, with
the same controls. The scene is a section on the left (on a phone, first), the activation, the
loadout table and the history on the right. The **PCs** box and **Dangers fight each other**
send themselves as soon as they change, as the sheet's boxes do; everything else is a button.
**Ctrl+R** presses **Activate Danger**. The session block, downloads, uploads and the colours
work as on the sheet, and a player's save uploaded here is refused the same way.

## Play in the browser

Prefer a web browser to the terminal? Start wid with `wid --web` (from a release download,
`.\wid.exe --web` on Windows or `./wid --web` on Linux and macOS, in the program's folder). Your
browser opens the sheet by itself. The window you started it from shows the address and must stay
open while you play; press **Ctrl+C** there to stop. Only this computer can reach the game.

The browser sheet has the same game controls as the terminal, with these differences:

- **Character** and **Session** are sections on one page instead of tabs, so there is no **C**
  or **S**.
- Nothing folds: the strain tracker, the items and the history are always shown, so there is no
  **T**, **I** or **Ctrl+L**.
- The only keys of its own are **Ctrl+R** and **Enter** in a text box, which sends what you
  typed. There is no **D** theme picker (the colours are below) and no **Ctrl+Q**: close the
  tab instead.
- The dice appear on the right (on a phone, straight after the options for the next test).
  **Repeat roll** or **Ctrl+R** rolls the last attribute again.
- **Save session** and **Load session** use the **Session file** box. **Export history** writes the
  Markdown to the **History file** box; **Download history** saves it through the browser.
- **Download save** saves the game through the browser, and **Upload a save** opens a save you
  pick, asking first if you would lose anything unsaved. Neither needs a path typed in.
- **Preview** is a tick box above the notes: tick it to see them formatted, untick it to edit.
- **Roll 1d6** sits beside **Repeat roll**.
- At 6 Resources, choose an effect in **Spend 6 Resources on** and press **Spend**.
- When something would be replaced or lost, a small box asks first, as in the terminal.
  Closing or reloading the page with unsaved changes asks too.
- The colours follow your browser's light or dark setting. **Colours** in the title band switches
  between Auto (your browser's setting), Light and Dark, and the browser remembers your choice.

Games saved in the browser open in the terminal, and the other way round. If the page says to
open wid from the address it printed, use the address shown in the window: it carries a key that
changes every time wid starts.

## Keys

| Key | What it does |
|---|---|
| **Ctrl+R** | Roll again with the last attribute |
| **C** / **S** | Open the Character / Session tab, then Tab or the arrow keys to move in |
| **T** / **I** | Fold or unfold the strain tracker / the items (Tech in Second Contact) |
| **D** | Pick a colour theme, which is remembered (the default, "danger", is cream and red) |
| **Ctrl+L** | Show or hide the history log |
| **Ctrl+P** | Search the commands: Save session, Load session, Undo and more (not over a dialog) |
| **Tab** / **Shift+Tab** | Move between controls |
| **Ctrl+Q** | Quit (asks first if anything is unsaved) |

The letter keys work when you are not typing in a text box. The bar at the bottom shows the
keys that work at that moment.

## Tips

- On Windows, Windows Terminal gives the best colours.
- A small terminal (80 by 24) works; the strain tracker and items start folded, so press **T** or
  **I** to open them.
- Your theme, last tab and folded sections are remembered between runs.
- `wid --self-test` checks the program, the browser version included, and reports which part
  failed, if any.
