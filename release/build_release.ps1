<#
.SYNOPSIS
    Builds the Windows release: wid-<version>-windows-<arch>.zip and a matching .sha256 in dist\.

.DESCRIPTION
    Needs uv (https://docs.astral.sh/uv/). The environment comes from uv.lock, so the build uses the
    same pinned versions as development. Run from anywhere:

        powershell -ExecutionPolicy Bypass -File release\build_release.ps1 [-Python 3.13] [-Smoke]

    The program is tested before it is packaged: `wid.exe --self-test` must pass. With -Smoke it
    is also driven through a real Windows pseudo console (release\smoke_windows.py), which needs
    the `smoke` dependency group (pywinpty).
#>
param([string]$Python, [switch]$Smoke)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit code $LASTEXITCODE): $Command" }
}

$pythonArgs = @()
if ($Python) { $pythonArgs = @("--python", $Python) }

Write-Host "==> Installing the pinned build environment"
$groups = @("--group", "release")
if ($Smoke) { $groups += @("--group", "smoke") }
Invoke-Checked { uv sync --locked --no-dev @groups --no-editable @pythonArgs }

# The installed version, which hatch-vcs took from the git tag (a dev version between tags).
$version = (uv run --no-sync @pythonArgs python -c "from importlib.metadata import version; print(version('wid'))").Trim()
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x86_64" }
$name = "wid-$version-windows-$arch"
Write-Host "==> Building $name"

Remove-Item -Recurse -Force build, "dist\wid", "dist\$name", "dist\$name.zip", "dist\$name.zip.sha256" -ErrorAction SilentlyContinue
Invoke-Checked { uv run --no-sync @pythonArgs pyinstaller release/wid.spec --noconfirm --log-level WARN }

$exe = Join-Path $root "dist\wid\wid.exe"
if (-not (Test-Path $exe)) { throw "PyInstaller did not produce $exe" }

Write-Host "==> Checking the built program"
$reported = (& $exe --version).Trim()
if ($reported -ne "wid $version") { throw "Built program reports '$reported', expected 'wid $version'" }
Invoke-Checked { & $exe --self-test }
if ($Smoke) {
    Write-Host "==> Driving the built program through a Windows pseudo console"
    Invoke-Checked { uv run --no-sync @pythonArgs python release/smoke_windows.py $exe }
}

Write-Host "==> Packaging"
$stage = Join-Path $root "dist\$name"
Copy-Item -Recurse "dist\wid" $stage
Copy-Item "release\README-windows.txt" (Join-Path $stage "README.txt")
Copy-Item "HOWTO.md" (Join-Path $stage "HOWTO.md")
$zip = Join-Path $root "dist\$name.zip"
Invoke-Checked { uv run --no-sync @pythonArgs python -m zipfile -c $zip $stage }
Remove-Item -Recurse -Force $stage

$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash *$name.zip" | Set-Content -Encoding ascii "$zip.sha256"

Write-Host ""
Write-Host "Done: $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
Write-Host "SHA-256: $hash"
