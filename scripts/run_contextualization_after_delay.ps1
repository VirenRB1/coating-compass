param(
    [Parameter(Mandatory = $true)]
    [DateTimeOffset]$StartAt,
    [ValidateSet("groq", "openai", "auto")]
    [string]$Provider = "auto"
)

$projectDirectory = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $projectDirectory "data/processed/contextual_dense_v1/auto_resume.log"
$pythonPath = Join-Path $projectDirectory ".venv/Scripts/python.exe"
$delaySeconds = [Math]::Ceiling(($StartAt - [DateTimeOffset]::Now).TotalSeconds)

"[$([DateTimeOffset]::Now.ToString('o'))] Scheduled $Provider contextualization for $($StartAt.ToString('o'))." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

if ($delaySeconds -gt 0) {
    Start-Sleep -Seconds $delaySeconds
}

Set-Location -LiteralPath $projectDirectory
"[$([DateTimeOffset]::Now.ToString('o'))] Starting $Provider contextualization." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

& $pythonPath -m src.data.contextualize_documents `
    --provider $Provider `
    --confirm-paid-calls 2>&1 |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

$exitCode = $LASTEXITCODE
"[$([DateTimeOffset]::Now.ToString('o'))] Contextualization exited with code $exitCode." |
    Out-File -LiteralPath $logPath -Encoding utf8 -Append

exit $exitCode
