wid - a terminal dice roller for We're in Danger

HOW TO RUN
  1. Unpack the download anywhere you like:   tar -xzf wid-VERSION-SYSTEM-ARCH.tar.gz
  2. Open a terminal, go to the unpacked folder and run:   ./wid
     To open a saved session straight away:   ./wid game.json
  Starting takes a second or two while the program unpacks itself.

MACOS: "WID CANNOT BE OPENED" OR "NOT VERIFIED"
  The program is not signed by Apple, so macOS blocks it the first time. Either run, in the
  folder:
    xattr -d com.apple.quarantine wid
  or try ./wid once, then open System Settings > Privacy & Security and choose "Open Anyway".

LINUX
  The program needs glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36 and later).

PLAY IN YOUR BROWSER
  In the folder, run:   ./wid --web
  Your browser opens the character sheet. Keep the terminal open while you play;
  press Ctrl+C in it to stop. Only this computer can reach the game.

HOW TO USE IT
  HOWTO.md in this folder explains the screen, the genre kits, saving and the keys.

CHECK THE DOWNLOAD
  Linux:  sha256sum -c wid-VERSION-SYSTEM-ARCH.tar.gz.sha256
  macOS:  shasum -a 256 -c wid-VERSION-SYSTEM-ARCH.tar.gz.sha256
  Run it next to the download; it must say OK.

CHECK THAT IT WORKS
  ./wid --version
  ./wid --self-test      (runs the program, browser version included, and reports ok or FAIL)

YOUR SETTINGS
  Theme, last tab and collapsed sections are kept in ~/.config/wid/settings.json (or under
  $XDG_CONFIG_HOME when it is set). Delete that file to start fresh. Saved sessions and exported
  history go where you choose. A game with unsaved changes is also kept in recovery.json there,
  and offered back if wid closes without a save.
