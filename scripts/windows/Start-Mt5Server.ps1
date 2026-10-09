#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallRoot)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
$lock = $null
$exitCode = 1
try {
    foreach ($folder in @('logs', 'run')) {
        if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot $folder) -PathType Container)) { throw "Missing installation directory: $folder" }
    }
    try { $lock = Open-Mt5ExclusiveLock (Join-Path $InstallRoot 'run\launcher.lock') }
    catch [IO.IOException] {
        # Duplicate trigger or concurrent activation: no second Python process is created.
        Write-Output 'This installation is already running or being activated; startup was skipped.'
        exit 0
    }
    $config = Read-Mt5Config $InstallRoot
    $release = Get-Mt5ReleasePath $InstallRoot $config.releaseName
    $python = Join-Path $release '.venv\Scripts\python.exe'
    $env:MT5_LOG_FILE = Join-Path $InstallRoot 'logs\server.log'
    $env:MT5_LOCK_FILE = Join-Path $InstallRoot 'run\server.lock'
    $env:MT5_JOURNAL_FILE = Join-Path $InstallRoot 'run\orders.jsonl'
    $env:PYTHONUNBUFFERED = '1'
    $serverArguments = @('-m', 'mcp_server_mt5', '--transport', 'http', '--host', '127.0.0.1', '--port', [string]$config.port, '--env-file', $config.envFile, '--mt5-path', $config.mt5Path)
    Write-Mt5LauncherLog $InstallRoot "Starting release $($config.releaseName); wrapper PID $PID; port $($config.port)."
    Push-Location -LiteralPath $release
    try {
        # Stay in the foreground so Task Scheduler observes the true runtime and exit code.
        & $python @serverArguments
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 1 }
    }
    finally { Pop-Location }
    Write-Mt5LauncherLog $InstallRoot "Release $($config.releaseName) exited with code $exitCode."
}
catch {
    $exitCode = 1
    # Do not print environment contents, account credentials, or a full configuration dump.
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    if ($null -ne $lock) {
        try { Write-Mt5LauncherLog $InstallRoot "Launcher failed: $($_.Exception.Message)" } catch { }
    }
}
finally {
    if ($null -ne $lock) { $lock.Dispose() }
}
exit $exitCode
