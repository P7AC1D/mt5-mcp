#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$PythonPath,
    [Parameter(Mandatory)][string]$ConfigPath,
    [switch]$Register,
    [switch]$PermissionsReviewed,
    [switch]$TerminalProfileProvisioned
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$PythonPath = Get-Mt5AbsolutePath $PythonPath
$ConfigPath = Get-Mt5AbsolutePath $ConfigPath
foreach ($path in @($PythonPath, $ConfigPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file missing: $path" }
}
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$runtime = Get-Mt5AbsolutePath $config.runtime_root
$envFile = Get-Mt5AbsolutePath $config.env_file
$terminal = Get-Mt5AbsolutePath $config.terminal_path
$release = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PythonPath))
$identity = 'NT SERVICE\MT5-MCP'
$binaryPath = (ConvertTo-Mt5CommandArgument $PythonPath) + ' -I -m mcp_server_mt5.windows_service --config ' + (ConvertTo-Mt5CommandArgument $ConfigPath)

Write-Output 'REVIEW ONLY unless -Register is supplied. No ACLs, accounts, passwords or MT5 profiles are changed by this script.'
Write-Output "Service: MT5-MCP; identity: $identity; own process; Automatic (boot); no stored Windows password."
Write-Output "Command: $binaryPath"
Write-Output 'Recovery: restart after 60s, 120s, then 300s (last action repeats); reset count after 86400s; nonzero service exits also recover.'
Write-Output "Required READ/EXECUTE: release $release and its base Python installation/DLLs; terminal executable $terminal."
Write-Output "Required READ: configuration $ConfigPath and environment file $envFile."
Write-Output "Required MODIFY, limited to service-owned state: $runtime\run and $runtime\logs."
Write-Output 'Separately provision a service-owned terminal profile/data directory with only the terminal permissions it needs.'
Write-Output 'Do not grant the service access to the whole Warren profile, copy terminal credential stores, enable desktop interaction, or use LocalSystem.'
Write-Output 'Provision protected code/config separately: service identity must not be able to modify executable code, service.json or server.env.'
Write-Output 'No firewall, URL, authentication, terminal trading settings, or logon-task changes are made.'

# Imports only. This invokes no MT5 initialize call and opens no listening socket.
& $PythonPath -I -m mcp_server_mt5.windows_service --config $ConfigPath --validate
if ($LASTEXITCODE -ne 0) { throw 'Service configuration validation failed; nothing registered.' }
if (-not $Register) { return }
if (-not $PermissionsReviewed -or -not $TerminalProfileProvisioned) {
    throw 'Review/provision the exact identity, file permissions and terminal profile first, then acknowledge both switches.'
}
$admin = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Registration requires an elevated administrator. This script does not self-elevate.'
}
if ($null -ne (Get-Service -Name 'MT5-MCP' -ErrorAction SilentlyContinue)) {
    throw 'MT5-MCP already exists. This installer never overwrites an existing service; use the documented stopped-service upgrade procedure.'
}
if (-not $PSCmdlet.ShouldProcess('MT5-MCP', "Register automatic native service as $identity (does NOT start it)")) { return }
$sc = Join-Path $env:SystemRoot 'System32\sc.exe'
# Native pywin32 calls preserve quoted paths on both PowerShell 5.1 and 7.
# Avoid sc.exe create's additional native-command-line quoting layer.
& $PythonPath -I -m mcp_server_mt5.service_install --config $ConfigPath --register
if ($LASTEXITCODE -ne 0) { throw 'SCM registration failed; inspect the reported SCM state before reboot.' }
& $sc qc MT5-MCP
& $sc qfailure MT5-MCP
& $sc qfailureflag MT5-MCP
Write-Output 'Registered, NOT STARTED. Automatic startup applies at next boot; complete validation before any reboot. Coordinate explicit Start-Service after the client and terminal cutover is approved.'
