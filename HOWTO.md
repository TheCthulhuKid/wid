# How to use wid

wid is a dice roller and tracker for **We're in Danger**.

## Start

1. Choose a **Genre kit** (top left). Core WiD is the default.
2. Give each attribute a different rank (1, 2 or 3) in the **Character** tab.
3. Press **Start game**. The ranks are locked until you change kit.
4. Press **Roll** beside an attribute. The result appears on the right.

**Load game** (next to Start game) opens a saved game instead. **Ctrl+Q** quits.

## Rolling

Set the options under the attributes, then press **Roll**:

- **Scared**: pick 0 to 3.
- **Assisted**: tick it when the roll is assisted.
- **Expertise**: tick it to include your expertise in the next roll.

**Assisted** and **Expertise** apply to one roll: they untick themselves afterwards, so tick them
again when they apply to the next one. **Scared** stays as you set it.

The line under the options shows the size of the pool (for example `Pool: 4d6`). The result
lists every die as *hit*, *miss* or *fumble* (green, yellow, red) with the totals below.

**Ctrl+R** rolls again with the last attribute you used, from anywhere in the program.

## Items and expertise

Type a name for each item under **Items** (**Appropriate Item** and **Inappropriate Item**).
After a roll:

1. Choose a die in **Apply to die**.
2. Press **+1 value** beside the item you are using.

Each item adds +1 to a single die, once per roll; its button greys out until your next roll. Use
the other item on the same die or another. **Undo** (beside **Apply to die**) takes back the last
item or expertise bonus and frees it again; press it again for the one before. A new roll clears
it. For expertise, name it and press **+1 hit** (or tick **Expertise** before rolling). Buttons
stay greyed out until the name is filled in and there is a roll to change.

## Genre kits

Every kit has the same screen. Each adds at most one thing:

| Kit | Attributes | Extra control |
|---|---|---|
| **Core WiD** | Athleticism, Composure, Reasoning | None |
| **Heckboy** | Aberrance, Ferocity, Savvy | **Power** list: None, Reliable, Erratic. The strain is added to the tracker for you. |
| **Second Contact** | Science, Culture, Muscle | **Tech** buttons (below) |
| **Oldheart** | Depravity, Hospitality, Fitness | Tick dice in the result, then **Reroll selected**. A running Corruption total is shown. |
| **Ball Season** | Propriety, Stoutness, Yearning | None |
| **This Isn't Happening** | Instincts, Endurance, Charity | None |

**Tech.** Press **Initialize / replace Tech** to set it up. The current strength is shown next to
it. Choose a die in **Tech target** before rolling to use it; at 0 the target list is disabled.
Press the button again to start over.

**Changing kit.** Pick another kit in **Genre kit**. The current roll is cleared, and you are
asked first if there is strain, Tech or Corruption to lose. The history stays. Set the ranks
again and press **Start game**.

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
- **Load game**: press it and a box asks for the path; it starts with the one from the Session
  tab. You are asked first if you would lose anything unsaved.
- **Export history**: writes all the rolls to a Markdown file you can read or share. The
  suggested name is your save file's name ending in `.md`.
- **New character**: clears the sheet for a new character in the same kit (after a character
  dies, for example): name, looks, nature, ranks, item and expertise names, strain, Scared and the
  current roll. The history, notes, session name and file path stay. You are asked first if
  there is anything to lose. Set the ranks again and press **Start game**.

A save includes everything on screen: kit, ranks, options, items, Tech, strain, Corruption,
notes, character details and the history.

## Keys

| Key | What it does |
|---|---|
| **Ctrl+R** | Roll again with the last attribute |
| **C** / **S** | Open the Character / Session tab, then Tab or the arrow keys to move in |
| **T** / **I** | Fold or unfold the strain tracker / the items |
| **D** | Pick a colour theme (it is remembered; the default is "danger", cream with red highlights) |
| **Ctrl+L** | Show or hide the history log |
| **Tab** / **Shift+Tab** | Move between controls |
| **Ctrl+Q** | Quit |

The letter keys work when you are not typing in a text box. The bar at the bottom shows the
keys that work at that moment.

## Tips

- On Windows, Windows Terminal gives the best colours.
- A small terminal (80 by 24) works; the strain tracker and items start folded, so press **T** or
  **I** to open them.
- Your theme, last tab and folded sections are remembered between runs.
- `wid --self-test` checks the program and reports which part failed, if any.
