# WiD Dice Roller

An unofficial dice roller for **[We're in Danger](https://thelollygaggers.com/were-in-danger/)**. It rolls your tests, keeps track of strain and wounds,
applies items and expertise, and saves your character and game so you can pick up next session.

## How to use it

**Read the [how-to](HOWTO.md).** It walks through starting a game, rolling, items, each
genre kit, the strain tracker, saving and loading, and the keys, with no technical knowledge
needed.

wid runs in a terminal, or in your web browser with `wid --web` (it stays on your computer; see
"Play in the browser" in the how-to).

## Get it (Windows)

1. Download `wid-<version>-windows-x86_64.zip` from the Releases page.
2. Unzip it anywhere.
3. Open the folder and run `wid.exe`, best in **Windows Terminal** (double-clicking works too).
   To play in your browser instead, run `.\wid.exe --web` in that folder.

Windows may say "Windows protected your PC", because the program is not code-signed. Choose
**More info**, then **Run anyway**. To check the download, compare
`Get-FileHash <zip> -Algorithm SHA256` with the `.sha256` file that comes with it.

Your theme and layout are remembered in `%APPDATA%\wid\settings.json`. Games are saved only
when you press **Save session**, to the file you choose.

## Other systems and developers

Running from Python, building a release, the project layout, and the file formats are in
[DEVELOPING.md](DEVELOPING.md).
