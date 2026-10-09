#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess, DefaultParameterSetName = 'Release')]
param(
    [Parameter(Mandatory)][string]$InstallRoot,
    [Parameter(Mandatory, ParameterSetName = 'Release')][string]$ReleaseName,
    [Parameter(Mandatory, ParameterSetName = 'Release')][string]$EnvFile,
    [Parameter(Mandatory, ParameterSetName = 'Release')][string]$Mt5Path,
    [Parameter(ParameterSetName = 'Release')][ValidateRange(1, 65535)][int]$Port = 8000,
    [Parameter(Mandatory, ParameterSetName = 'Previous')][switch]$Previous
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'run') -PathType Container)) {
    throw 'Installation is not staged. Run Stage-Mt5Release.ps1 first.'
}
if (-not $PSCmdlet.ShouldProcess($InstallRoot, 'Activate a staged release and save the previous configuration for rollback')) { return }
$launcherLock = $null
$serverLock = $null
try {
    # Shares the launcher gate; activation and startup cannot race.
    $launcherLock = Open-Mt5ExclusiveLock (Join-Path $InstallRoot 'run\launcher.lock')
    $serverLock = Open-Mt5ExclusiveLock (Join-Path $InstallRoot 'run\server.lock')
    $currentPath = Join-Path $InstallRoot 'current.json'
    $current = if (Test-Path -LiteralPath $currentPath) { Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json } else { $null }
    if ($null -ne $current -and $current.schemaVersion -ne 1) { throw 'Unsupported current configuration version; review it before changing releases.' }
    if ($Previous) { $next = Read-Mt5Config -InstallRoot $InstallRoot -FileName 'previous.json' }
    else {
        $next = [ordered]@{
            schemaVersion = 1
            releaseName = $ReleaseName
            envFile = Get-Mt5AbsolutePath $EnvFile
            mt5Path = Get-Mt5AbsolutePath $Mt5Path
            host = '127.0.0.1'
            port = $Port
        }
        Assert-Mt5ReleaseName $ReleaseName
        foreach ($path in @($next.envFile, $next.mt5Path, (Join-Path (Get-Mt5ReleasePath $InstallRoot $ReleaseName) 'release.json'), (Join-Path (Get-Mt5ReleasePath $InstallRoot $ReleaseName) '.venv\Scripts\python.exe'))) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
        }
    }
    if ($null -ne $current) {
        if ($current.releaseName -eq $next.releaseName -and $current.envFile -eq $next.envFile -and $current.mt5Path -eq $next.mt5Path -and $current.port -eq $next.port) {
            Write-Output 'That release and configuration are already active. Rollback history was preserved.'
            return
        }
        Write-Mt5JsonAtomic -Path (Join-Path $InstallRoot 'previous.json') -Value $current
    }
    Write-Mt5JsonAtomic -Path $currentPath -Value $next
    Write-Output "Activated $($next.releaseName). Re-register the task to use this release's launcher, then start it and run Test-Mt5Health.ps1."
}
catch [IO.IOException] {
    throw "Cannot activate while a launcher/server is running or a deployment file is unavailable. Stop this installation, confirm its processes have exited, and retry. Detail: $($_.Exception.Message)"
}
finally {
    if ($null -ne $serverLock) { $serverLock.Dispose() }
    if ($null -ne $launcherLock) { $launcherLock.Dispose() }
}
