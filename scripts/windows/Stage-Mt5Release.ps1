#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$SourcePath,
    [Parameter(Mandatory)][string]$InstallRoot,
    [Parameter(Mandatory)][string]$ReleaseName,
    [Parameter(Mandatory)][string]$PythonPath,
    [Parameter(Mandatory)][string]$UvPath
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$SourcePath = Get-Mt5AbsolutePath $SourcePath
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
$PythonPath = Get-Mt5AbsolutePath $PythonPath
$UvPath = Get-Mt5AbsolutePath $UvPath
$release = Get-Mt5ReleasePath $InstallRoot $ReleaseName
if ($InstallRoot.Equals($SourcePath, [StringComparison]::OrdinalIgnoreCase) -or $InstallRoot.StartsWith($SourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'InstallRoot must be separate from, and outside, the source checkout.'
}
foreach ($path in @($PythonPath, $UvPath, (Join-Path $SourcePath 'pyproject.toml'), (Join-Path $SourcePath 'uv.lock'))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
}
foreach ($relative in @('src\mcp_server_mt5', 'scripts\windows')) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourcePath $relative) -PathType Container)) { throw "Required source directory missing: $relative" }
}
if (Test-Path -LiteralPath $release) { throw "Release already exists. Choose a new release name: $release" }
if (-not $PSCmdlet.ShouldProcess($release, 'Copy reviewed source and install its locked dependencies with uv')) { return }

New-Item -ItemType Directory -Path (Split-Path -Parent $release) -Force | Out-Null
# Reserve the release name atomically; simultaneous staging must not share it.
New-Item -ItemType Directory -Path $release -ErrorAction Stop | Out-Null
foreach ($folder in @('config', 'logs', 'run')) {
    New-Item -ItemType Directory -Path (Join-Path $InstallRoot $folder) -Force | Out-Null
}
# Do not copy .env, Git history, cached environments, runtime state, or account credentials.
foreach ($name in @('pyproject.toml', 'uv.lock', 'README.md', 'LICENSE')) {
    Copy-Item -LiteralPath (Join-Path $SourcePath $name) -Destination (Join-Path $release $name)
}
foreach ($relative in @('src\mcp_server_mt5', 'scripts\windows')) {
    $sourceDirectory = Join-Path $SourcePath $relative
    $destinationDirectory = Join-Path $release $relative
    Get-ChildItem -LiteralPath $sourceDirectory -File -Recurse | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -notin @('.pyc', '.pyo') -and $_.Name -notlike '.env*'
    } | ForEach-Object {
        $relativeFile = $_.FullName.Substring($sourceDirectory.Length).TrimStart([char[]]'\/')
        $destination = Join-Path $destinationDirectory $relativeFile
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    }
}
foreach ($name in @('windows-deployment.md', 'windows-service.md')) {
    $docs = Join-Path (Join-Path $SourcePath 'docs') $name
    if (Test-Path -LiteralPath $docs -PathType Leaf) {
        New-Item -ItemType Directory -Path (Join-Path $release 'docs') -Force | Out-Null
        Copy-Item -LiteralPath $docs -Destination (Join-Path (Join-Path $release 'docs') $name)
    }
}
# A venv is not relocatable. Build directly at its final, unique release path.
$previousEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $release '.venv'
    Push-Location -LiteralPath $release
    try {
        & $UvPath sync --locked --no-dev --no-editable --no-managed-python --python $PythonPath
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed (exit $LASTEXITCODE). The incomplete release cannot be activated." }
        $interpreter = Join-Path $release '.venv\Scripts\python.exe'
        & $interpreter -c "import struct, MetaTrader5, mcp_server_mt5; assert struct.calcsize('P') == 8, '64-bit Python is required'"
        if ($LASTEXITCODE -ne 0) { throw 'Read-only import/architecture validation failed. The incomplete release cannot be activated.' }
    }
    finally { Pop-Location }
}
finally { $env:UV_PROJECT_ENVIRONMENT = $previousEnvironment }
$manifest = [ordered]@{
    schemaVersion = 1
    releaseName = $ReleaseName
    stagedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
    lockSha256 = (Get-FileHash -LiteralPath (Join-Path $release 'uv.lock') -Algorithm SHA256).Hash
}
Write-Mt5JsonAtomic -Path (Join-Path $release 'release.json') -Value $manifest
Write-Output "Staged $release. Nothing was started or activated; no terminal connection or trade was attempted."
