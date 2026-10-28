wid - a dice roller for We're in Danger, in the terminal or a browser

HOW TO RUN
  1. Unzip this folder anywhere you like.
  2. Open Windows Terminal or PowerShell, go to the folder and run:   .\wid.exe
     (Double-clicking wid.exe also works. Windows Terminal looks best.)
  3. To open a saved session straight away:   .\wid.exe game.json
     or right-click the save, choose "Open with" and pick wid.exe.

"WINDOWS PROTECTED YOUR PC"
  The program is not code-signed, so Windows SmartScreen may warn the first time.
  Choose "More info", then "Run anyway".

RUNNING THE GAME
  The Game Master's screen, with the Dangers instead of a character:   .\wid.exe --gm
  The same in your browser:   .\wid.exe --web --gm

PLAY IN YOUR BROWSER
  In the folder, run:   .\wid.exe --web
  Your browser opens the character sheet. Keep the window open while you play;
  press Ctrl+C in it to stop. Only this computer can reach the game.

  To start it with a double-click, make a shortcut (double-clicking wid.exe itself
  always opens the terminal version):
    1. Right-click wid.exe and choose "Create shortcut".
    2. Right-click the new shortcut, choose "Properties", and add  --web  to the end
       of "Target", for example:   "C:\Games\wid\wid.exe" --web
    3. Double-click the shortcut. A console window opens next to the browser: that
       window is the game, so leave it open and close it (or press Ctrl+C) to stop.

HOW TO USE IT
  HOWTO.md in this folder explains the screen, the genre kits, saving and the keys.

CHECK THE DOWNLOAD
  In PowerShell:  Get-FileHash .\wid-VERSION-windows-x86_64.zip -Algorithm SHA256
  The result must match the contents of the .sha256 file next to the download.

CHECK THAT IT WORKS
  .\wid.exe --version
  .\wid.exe --self-test      (runs the program, browser version included, and reports ok or FAIL)

YOUR SETTINGS
  Theme, last tab and collapsed sections are kept in %APPDATA%\wid\settings.json.
  Delete that file to start fresh. Saved sessions and exported history go where you choose.
  A game with unsaved changes is also kept in recovery.json there, and offered back if wid
  closes without a save.
