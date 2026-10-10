#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory)][string]$ConfigPath)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$ConfigPath = Get-Mt5AbsolutePath $ConfigPath
$service = Get-CimInstance Win32_Service -Filter "Name='MT5-MCP'"
if ($null -eq $service) { Write-Output 'MT5-MCP is not registered.'; return }
if ($service.State -ne 'Stopped') { throw 'Stop this service gracefully and verify the old process exited before removal. No process will be killed.' }
$expectedArgument = '--config ' + (ConvertTo-Mt5CommandArgument $ConfigPath)
$unquotedArgument = '--config ' + $ConfigPath
if ((-not $service.PathName.EndsWith($expectedArgument, [StringComparison]::OrdinalIgnoreCase) -and -not $service.PathName.EndsWith($unquotedArgument, [StringComparison]::OrdinalIgnoreCase)) -or $service.PathName -notmatch ' -I -m mcp_server_mt5\.windows_service ') {
    throw 'Refusing to remove a service whose command does not match this configuration and native host.'
}
if ($PSCmdlet.ShouldProcess('MT5-MCP', 'Remove stopped SCM registration only; retain all configuration, terminal data, logs and journal')) {
    & (Join-Path $env:SystemRoot 'System32\sc.exe') delete MT5-MCP
    if ($LASTEXITCODE -ne 0) { throw 'SCM removal failed; no data files were removed.' }
}
