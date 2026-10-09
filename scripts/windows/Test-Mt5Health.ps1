#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InstallRoot,
    [ValidateRange(1, 60)][int]$TimeoutSeconds = 5,
    [ValidateRange(0, 600)][int]$WaitSeconds = 0,
    [Security.SecureString]$HttpToken
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
$config = Read-Mt5Config $InstallRoot
$baseUri = "http://127.0.0.1:$($config.port)"
$headers = @{}
if ($null -ne $HttpToken) {
    $buffer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($HttpToken)
    try { $headers.Authorization = 'Bearer ' + [Runtime.InteropServices.Marshal]::PtrToStringBSTR($buffer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($buffer) }
}
elseif (-not [string]::IsNullOrEmpty($env:MT5_HTTP_TOKEN)) { $headers.Authorization = 'Bearer ' + $env:MT5_HTTP_TOKEN }
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($WaitSeconds)
do {
    $results = @()
    foreach ($endpoint in @('/healthz', '/readyz')) {
        try {
            $response = Invoke-WebRequest -Uri ($baseUri + $endpoint) -Method Get -Headers $headers -UseBasicParsing -TimeoutSec $TimeoutSeconds -MaximumRedirection 0
            $ok = [int]$response.StatusCode -eq 200
            # A JSON response distinguishes the server's probes from a generic HTML listener.
            $payload = $response.Content | ConvertFrom-Json
            if ($null -eq $payload -or $payload -isnot [pscustomobject]) { throw 'Expected a JSON object from the health endpoint.' }
            $results += [pscustomobject]@{ endpoint = $endpoint; ok = $ok; statusCode = [int]$response.StatusCode; detail = 'JSON response received' }
        }
        catch {
            $results += [pscustomobject]@{ endpoint = $endpoint; ok = $false; statusCode = $null; detail = $_.Exception.Message }
        }
    }
    $healthy = @($results | Where-Object { -not $_.ok }).Count -eq 0
    if ($healthy -or [DateTimeOffset]::UtcNow -ge $deadline) { break }
    Start-Sleep -Seconds 2
} while ($true)
$headers.Clear()
$results | Format-Table -AutoSize | Out-Host
if (-not $healthy) {
    Write-Error 'Health/readiness verification failed. No orders, account changes, restarts, or repairs were attempted.' -ErrorAction Continue
    exit 1
}
Write-Output "Healthy and ready at $baseUri/mcp. Probes used GET only; no MCP tools or orders were called."
exit 0
