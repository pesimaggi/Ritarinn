<#
.SYNOPSIS
    Ritarinn start for Windows.

.DESCRIPTION
    Runs the backend and the frontend dev server, both bound to loopback, and
    shuts both down cleanly on Ctrl-C.

.NOTES
    Pure ASCII on purpose - see the note in setup.ps1.
#>

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Syndarumhverfi fannst ekki. Keyrdu .\setup.ps1 fyrst.' -ForegroundColor Red
    Write-Host 'Virtual environment not found. Run .\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path 'frontend\node_modules')) {
    Write-Host 'npm-pakkar fundust ekki. Keyrdu .\setup.ps1 fyrst.' -ForegroundColor Red
    Write-Host 'Frontend dependencies not found. Run .\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

$backend = $null
$frontend = $null

try {
    $backend = Start-Process -FilePath $venvPython -ArgumentList '-m', 'ritarinn' `
        -NoNewWindow -PassThru
    $frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
        -WorkingDirectory (Join-Path $PSScriptRoot 'frontend') -NoNewWindow -PassThru

    Write-Host "`nRitarinn"
    Write-Host '  Vidmot:  http://127.0.0.1:5173'
    Write-Host '  Bakendi: http://127.0.0.1:8756'
    Write-Host '  Unnid stadbundid - enginn texti fer af thessari tolvu.' -ForegroundColor Green
    Write-Host ''

    # Return as soon as either process exits, so a crashed backend does not
    # leave a frontend running against nothing.
    while ($true) {
        if ($backend.HasExited -or $frontend.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
} finally {
    foreach ($process in @($frontend, $backend)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
