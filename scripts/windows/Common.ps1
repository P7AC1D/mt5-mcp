# Shared helpers. Dot-source this file; it makes no external changes itself.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Mt5Windows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'These deployment scripts require Windows PowerShell 5.1 or PowerShell 7 on Windows.'
    }
}

function Get-Mt5AbsolutePath {
    param([Parameter(Mandatory)][string]$Path)
    # Reject drive-relative paths (C:folder), environment placeholders, and network shares.
    if ($Path -notmatch '^[A-Za-z]:[\\/]') {
        throw "Use an absolute local drive path, not a relative path or network share: $Path"
    }
    $fullPath = [IO.Path]::GetFullPath($Path)
    if ($fullPath.Length -le 3) { throw 'Use a specific directory or file, not a drive root.' }
    return $fullPath.TrimEnd([char[]]'\/')
}

function Assert-Mt5ReleaseName {
    param([Parameter(Mandatory)][string]$Name)
    if ($Name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$' -or $Name -in @('.', '..')) {
        throw 'ReleaseName must be 1-80 letters, numbers, dots, underscores, or hyphens, starting with a letter or number.'
    }
}

function Get-Mt5ReleasePath {
    param([Parameter(Mandatory)][string]$InstallRoot, [Parameter(Mandatory)][string]$ReleaseName)
    Assert-Mt5ReleaseName $ReleaseName
    return Join-Path (Join-Path $InstallRoot 'releases') $ReleaseName
}

function Read-Mt5Config {
    param([Parameter(Mandatory)][string]$InstallRoot, [string]$FileName = 'current.json')
    $path = Join-Path $InstallRoot $FileName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Deployment configuration is missing: $path. Run Set-Mt5Release.ps1 first."
    }
    $config = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($config.schemaVersion -ne 1) { throw 'Unsupported deployment configuration version.' }
    Assert-Mt5ReleaseName $config.releaseName
    if ($config.host -ne '127.0.0.1') { throw 'The deployment launcher only supports the loopback address 127.0.0.1.' }
    if ([int]$config.port -lt 1 -or [int]$config.port -gt 65535) { throw 'Invalid configured port.' }
    foreach ($name in @('envFile', 'mt5Path')) {
        $value = Get-Mt5AbsolutePath $config.$name
        if (-not (Test-Path -LiteralPath $value -PathType Leaf)) { throw "Missing configured $name file: $value" }
    }
    $release = Get-Mt5ReleasePath $InstallRoot $config.releaseName
    if (-not (Test-Path -LiteralPath (Join-Path $release 'release.json') -PathType Leaf)) {
        throw "Release has no successful staging manifest: $release"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $release '.venv\Scripts\python.exe') -PathType Leaf)) {
        throw "Release interpreter is missing: $release"
    }
    return $config
}

function Write-Mt5JsonAtomic {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value)
    # Same-volume replacement: readers see the old or new complete JSON, never a partial write.
    $temporary = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        $json = $Value | ConvertTo-Json -Depth 10
        [IO.File]::WriteAllText($temporary, $json, (New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary, $Path, $null) }
        else { [IO.File]::Move($temporary, $Path) }
    }
    finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Open-Mt5ExclusiveLock {
    param([Parameter(Mandatory)][string]$Path)
    # The open handle is the lock. A file left after a crash is harmless; never delete it to unlock.
    return [IO.File]::Open($Path, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
}

function ConvertTo-Mt5CommandArgument {
    param([Parameter(Mandatory)][string]$Value)
    # Windows paths cannot contain quotes. Doubling final backslashes avoids escaping the closing quote.
    if ($Value.Contains('"') -or $Value.Contains("`r") -or $Value.Contains("`n")) {
        throw 'Quotes or newlines are not supported in task argument paths.'
    }
    return '"' + ($Value -replace '(\\+)$', '$1$1') + '"'
}

function Write-Mt5LauncherLog {
    param([Parameter(Mandatory)][string]$InstallRoot, [Parameter(Mandatory)][string]$Message)
    $path = Join-Path $InstallRoot 'logs\launcher.log'
    if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -ge 1048576) {
        for ($index = 3; $index -ge 1; $index--) {
            $source = if ($index -eq 1) { $path } else { "$path.$($index - 1)" }
            if (Test-Path -LiteralPath $source) { Move-Item -LiteralPath $source -Destination "$path.$index" -Force }
        }
    }
    Add-Content -LiteralPath $path -Value "$([DateTimeOffset]::Now.ToString('o')) $Message" -Encoding UTF8
}
