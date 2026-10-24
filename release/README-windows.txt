wid - a terminal dice roller for We're in Danger

HOW TO RUN
  1. Unzip this folder anywhere you like.
  2. Open Windows Terminal or PowerShell, go to the folder and run:   .\wid.exe
     (Double-clicking wid.exe also works. Windows Terminal looks best.)

"WINDOWS PROTECTED YOUR PC"
  The program is not code-signed, so Windows SmartScreen may warn the first time.
  Choose "More info", then "Run anyway".

HOW TO USE IT
  HOWTO.md in this folder explains the screen, the genre kits, saving and the keys.

CHECK THE DOWNLOAD
  In PowerShell:  Get-FileHash .\wid-VERSION-windows-x86_64.zip -Algorithm SHA256
  The result must match the contents of the .sha256 file next to the download.

CHECK THAT IT WORKS
  .\wid.exe --version
  .\wid.exe --self-test      (runs the program without a terminal and reports ok or FAIL)

YOUR SETTINGS
  Theme, last tab and collapsed sections are kept in %APPDATA%\wid\settings.json.
  Delete that file to start fresh. Saved games and exported history go where you choose.
