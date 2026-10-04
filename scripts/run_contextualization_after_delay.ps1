param(
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$StartAt,
    [string]$Params = "params.yaml"
)

$projectDirectory = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectDirectory ".venv/Scripts/python.exe"
Set-Location -LiteralPath $projectDirectory
$artifactDirectory = & $pythonPath -c "import sys; from src.config import load_params, path; load_params(sys.argv[1]); print(path('contextual_artifacts'))" $Params
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
$logPath = Join-Path $artifactDirectory "auto_resume.log"
$delaySeconds = [Math]::Ceiling(($StartAt - [DateTimeOffset]::Now).TotalSeconds)

"[$([DateTimeOffset]::Now.ToString('o'))] Scheduled contextualization using $Params for $($StartAt.ToString('o'))." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

if ($delaySeconds -gt 0) {
    Start-Sleep -Seconds $delaySeconds
}

Set-Location -LiteralPath $projectDirectory
"[$([DateTimeOffset]::Now.ToString('o'))] Starting contextualization using $Params." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

& $pythonPath -m src.data.contextualize_documents `
    --params $Params `
    --confirm-paid-calls 2>&1 |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

$exitCode = $LASTEXITCODE
"[$([DateTimeOffset]::Now.ToString('o'))] Contextualization exited with code $exitCode." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

exit $exitCode
