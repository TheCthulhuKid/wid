# WiD Dice Roller

An unofficial dice roller for **[We're in Danger](https://thelollygaggers.com/were-in-danger/)**.
It rolls your tests, keeps track of strain and wounds, applies items and expertise, and saves your
character and game so you can pick up next session.

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
4. To open a saved session straight away, run `.\wid.exe game.json`, or right-click the save,
   choose **Open with** and pick `wid.exe`.

Windows may say "Windows protected your PC", because the program is not code-signed. Choose
**More info**, then **Run anyway**. To check the download, compare
`Get-FileHash <zip> -Algorithm SHA256` with the `.sha256` file that comes with it.

Your theme and layout are remembered in `%APPDATA%\wid\settings.json`. Games are saved only
when you press **Save session**, to the file you choose. Until then wid keeps a recovery copy
beside the settings, and offers it back if wid closed without a save.

## Get it (Linux and macOS)

1. Download `wid-<version>-linux-x86_64.tar.gz` or `wid-<version>-macos-arm64.tar.gz` (Apple
   silicon) from the Releases page.
2. Unpack it with `tar -xzf <file>` and run `./wid` in the new folder from a terminal, or
   `./wid --web` for the browser. `./wid game.json` opens a saved session straight away.

macOS blocks the program the first time because it is not signed by Apple: run
`xattr -d com.apple.quarantine wid` in the folder, or choose **Open Anyway** under System
Settings > Privacy & Security. The Linux build needs glibc 2.35 or newer (Ubuntu 22.04 and
later). Settings are kept in `~/.config/wid/settings.json`. The `README.txt` in the download
explains checking the `.sha256` file.

## Running from Python and developers

Running from Python, building a release, the project layout, and the file formats are in
[DEVELOPING.md](DEVELOPING.md).
