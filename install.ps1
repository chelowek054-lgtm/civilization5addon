# Installs the in-game logger into Civ 5 (Brave New World UI) and turns on Lua logging.
# The logger is UI-only, so it works in multiplayer without desyncs.
# Run again after game updates. Use -Uninstall to restore the original files.
param(
    [string]$GameDir = "D:\SteamLibrary\steamapps\common\Sid Meier's Civilization V",
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$ui = Join-Path $GameDir "Assets\DLC\Expansion2\UI\InGame"
$inGame = Join-Path $ui "InGame.xml"
$backup = "$inGame.civstats-backup"
$line = "`t<LuaContext FileName=`"CivStatsLogger`" ID=`"CivStatsLogger`" Hidden=`"1`"/>`r`n"

# Remove the old DLC-style install from earlier versions
$oldDlc = Join-Path $GameDir "Assets\DLC\CivStats"
if (Test-Path $oldDlc) { Remove-Item $oldDlc -Recurse -Force }

if ($Uninstall) {
    if (Test-Path $backup) { Move-Item $backup $inGame -Force }
    Remove-Item "$ui\CivStatsLogger.lua", "$ui\CivStatsLogger.xml" -ErrorAction SilentlyContinue
    Write-Host "Uninstalled."
    return
}

Copy-Item "$PSScriptRoot\game\UI\CivStatsLogger.lua", "$PSScriptRoot\game\UI\CivStatsLogger.xml" $ui -Force
# The game's Lua 5.1 fails on a UTF-8 BOM ("unexpected symbol near '�'"): make sure there is none
foreach ($f in "$ui\CivStatsLogger.lua", "$ui\CivStatsLogger.xml") {
    $b = [IO.File]::ReadAllBytes($f)
    if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
        [IO.File]::WriteAllBytes($f, $b[3..($b.Length - 1)])
    }
}

if (-not (Test-Path $backup)) { Copy-Item $inGame $backup }
$xml = Get-Content $backup -Raw
$idx = $xml.LastIndexOf("</Context>")
$xml = $xml.Substring(0, $idx) + $line + $xml.Substring($idx)
[IO.File]::WriteAllText($inGame, $xml, (New-Object Text.UTF8Encoding $false))

# Enable Lua.log
$cfg = Join-Path ([Environment]::GetFolderPath('MyDocuments')) "My Games\Sid Meier's Civilization 5\config.ini"
if (Test-Path $cfg) {
    $c = Get-Content $cfg -Raw
    $c = $c -replace 'LoggingEnabled\s*=\s*0', 'LoggingEnabled = 1'
    [IO.File]::WriteAllText($cfg, $c)
}
Write-Host "Installed into $ui; logging enabled."
