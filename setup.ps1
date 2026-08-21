<#
.SYNOPSIS
    Ritarinn setup for Windows.

.DESCRIPTION
    Creates a Python virtual environment, installs backend and frontend
    dependencies, verifies GreynirCorrect actually works, and reports whether
    Ollama is present.

    It deliberately does NOT download any language model. Nothing
    multi-gigabyte is fetched on your behalf.

.NOTES
    This file is intentionally pure ASCII. Windows PowerShell 5.1 decodes a
    BOM-less .ps1 using the system ANSI code page, which mangles Icelandic
    characters. Console messages therefore use ASCII transliteration, and the
    Icelandic test sentence below is written with \u escapes so it survives
    regardless of how the file is decoded.
#>

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Write-Step { param($Message) Write-Host "`n==> $Message" -ForegroundColor White }
function Write-Ok   { param($Message) Write-Host "  [ok] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "  [--] $Message" -ForegroundColor Yellow }
function Write-Fail { param($Message) Write-Host "  [!!] $Message" -ForegroundColor Red }

# --- prerequisites ------------------------------------------------------------

Write-Step 'Athuga forkroefur / Checking prerequisites'

$python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    # 'py' needs a version argument; the rest are invoked directly.
    $exe = $command.Source
    & $exe -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $exe; break }
}

if (-not $python) {
    Write-Fail 'Python 3.10 eda nyrri fannst ekki. / Python 3.10+ not found.'
    Write-Host '     https://www.python.org/downloads/'
    exit 1
}
Write-Ok "Python: $(& $python --version)"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Fail 'Node.js fannst ekki. / Node.js not found.'
    Write-Host '     https://nodejs.org/ (18 eda nyrra / 18 or newer)'
    exit 1
}
Write-Ok "Node.js: $(node --version)"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Fail 'npm fannst ekki. / npm not found.'
    exit 1
}

# --- backend ------------------------------------------------------------------

Write-Step 'Setja upp bakenda / Installing backend'

if (-not (Test-Path '.venv')) {
    & $python -m venv .venv
    Write-Ok 'Syndarumhverfi buid til / virtual environment created'
} else {
    Write-Ok 'Syndarumhverfi til stadar / virtual environment exists'
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Fail "Fann ekki $venvPython"
    exit 1
}

& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r backend/requirements-dev.txt
& $venvPython -m pip install --quiet -e backend
Write-Ok 'Python-pakkar settir upp / Python packages installed'

# --- verify GreynirCorrect ----------------------------------------------------

Write-Step 'Stadfesta GreynirCorrect / Verifying GreynirCorrect'

# Written to a temporary file rather than piped, so the Icelandic test sentence
# survives PowerShell's stdin encoding.
$verifyScript = @'
import sys

try:
    import reynir_correct
except Exception as exc:
    print(f"    import failed: {exc}", file=sys.stderr)
    raise SystemExit(1)

# Escaped so this text is unaffected by how the .ps1 was decoded.
SENTENCE = "\u00deinngi\u00f0 sam\u00feikkti til\u00f6guna."
EXPECTED = ("\u00deinngi\u00f0", "\u00deingi\u00f0")

api = reynir_correct.GreynirCorrectAPI.from_options()
result = api.correct(SENTENCE)
found = {
    annotation.original: annotation.suggest
    for sentence in result.sentences
    for annotation in (sentence.annotations or [])
}
if found.get(EXPECTED[0]) != EXPECTED[1]:
    print(f"    unexpected output: {found}", file=sys.stderr)
    raise SystemExit(1)
print(f"    reynir-correct {reynir_correct.__version__}: spelling correction works")
'@

$verifyPath = Join-Path ([System.IO.Path]::GetTempPath()) 'ritarinn_verify.py'
Set-Content -Path $verifyPath -Value $verifyScript -Encoding UTF8
try {
    & $venvPython $verifyPath
    if ($LASTEXITCODE -ne 0) { throw 'verification failed' }
    Write-Ok 'GreynirCorrect tilbuid / ready'
} catch {
    Write-Fail 'GreynirCorrect virkar ekki. / GreynirCorrect is not working.'
    exit 1
} finally {
    Remove-Item $verifyPath -ErrorAction SilentlyContinue
}

# --- frontend -----------------------------------------------------------------

Write-Step 'Setja upp vidmot / Installing frontend'

Push-Location frontend
try {
    npm install --silent
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
} finally {
    Pop-Location
}
Write-Ok 'npm-pakkar settir upp / npm packages installed'

# --- optional: Ollama ---------------------------------------------------------

Write-Step 'Leita ad Ollama / Looking for Ollama'

$ollamaUrl = if ($env:RITARINN_OLLAMA_URL) { $env:RITARINN_OLLAMA_URL } else { 'http://127.0.0.1:11434' }
try {
    Invoke-WebRequest -Uri "$ollamaUrl/api/tags" -TimeoutSec 2 -UseBasicParsing | Out-Null
    Write-Ok "Ollama fannst a $ollamaUrl / found"
    Write-Warn 'Ekkert likan er valid. Yfirlestur virkar an thess. / No model selected; proofreading works without one.'
} catch {
    Write-Warn 'Ollama fannst ekki. / not found.'
    Write-Host '    Yfirlestur virkar an Ollama. Thad tharf adeins fyrir samantekt og einfoldun (afangi 2).' -ForegroundColor DarkGray
    Write-Host '    Proofreading works without it; it is only needed for summarization and simplification.' -ForegroundColor DarkGray
}

# --- optional: the neural corrector -------------------------------------------
#
# Reported, never installed. It needs PyTorch and a 2.3 GB download, and
# proofreading does not depend on either.

Write-Step 'Valfrjals tauganetsleidretting / Optional neural correction'

& $venvPython -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("torch") and importlib.util.find_spec("transformers") else 1)' 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok 'PyTorch og Transformers til stadar / present'
    Write-Host '    Saektu likanid med: .venv\Scripts\python.exe scripts\install_byt5.py' -ForegroundColor DarkGray
} else {
    Write-Warn 'Ekki uppsett. Yfirlestur virkar an hennar. / Not installed; proofreading works without it.'
    Write-Host '    Til ad profa hana: pip install -r backend\requirements-byt5.txt' -ForegroundColor DarkGray
    Write-Host '    Sja README, kaflann um ByT5. / See the ByT5 section in the README.' -ForegroundColor DarkGray
}

Write-Host "`nUppsetningu lokid. / Setup complete." -ForegroundColor Green
Write-Host "Keyrdu .\start.ps1 og opnadu http://127.0.0.1:5173`n"
