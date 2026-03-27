param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Source = "manual-smoke",
    [string]$IdempotencyKey = ("smoke-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssffff")),
    [string]$Body = @"
Smoke test prompt from HumanLoop pass 5.

1. Copy this prompt from the local inbox.
2. Paste it into the manual handoff target.
3. Return to the inbox and click Complete or Dismiss.
"@
)

$payload = @{
    body = $Body
    source = $Source
    idempotency_key = $IdempotencyKey
    metadata = @{
        kind = "smoke"
        created_by = "scripts/enqueue-sample-prompt.ps1"
    }
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/prompts" `
        -ContentType "application/json" `
        -Body $payload
} catch {
    Write-Error "Failed to enqueue the sample prompt at $BaseUrl/api/prompts. Start the app first and retry."
    throw
}

Write-Host "Enqueued sample prompt."
Write-Host "  id:  $($response.id)"
Write-Host "  seq: $($response.seq)"
Write-Host "  url: $BaseUrl/inbox"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open $BaseUrl/inbox"
Write-Host "  2. Copy the prompt from the inbox"
Write-Host "  3. Complete or Dismiss it explicitly after the manual handoff"
