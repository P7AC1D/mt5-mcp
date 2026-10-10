#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$InstallRoot,
    [switch]$ApplyPermissionPlan
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
$programData = [IO.Path]::GetFullPath($env:ProgramData).TrimEnd('\')
if (-not $InstallRoot.StartsWith($programData + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose a new dedicated installation directory under ProgramData; existing user/application directories are never re-ACLd.'
}
if (Test-Path -LiteralPath $InstallRoot) { throw 'InstallRoot already exists. This script never changes permissions on an existing directory tree.' }
$ancestor = Split-Path -Parent $InstallRoot
while ($ancestor) {
    if (Test-Path -LiteralPath $ancestor) {
        $item = Get-Item -LiteralPath $ancestor -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse-point ancestors are not supported for service provisioning.' }
    }
    $ancestor = Split-Path -Parent $ancestor
}
$sc = Join-Path $env:SystemRoot 'System32\sc.exe'
$sidOutput = & $sc showsid MT5-MCP
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the MT5-MCP virtual service SID.' }
$sid = [regex]::Match(($sidOutput -join ' '), 'S-1-5-80-(?:\d+-){4}\d+').Value
if (-not $sid) { throw 'Could not parse the virtual service SID.' }
Write-Output "Permission plan for NEW directory only: $InstallRoot"
Write-Output "Identity: NT SERVICE\MT5-MCP ($sid); no password or Windows user is created."
Write-Output 'Root and descendants: SYSTEM/Administrators FullControl; service ReadAndExecute. Inheritance from the ProgramData parent is disabled on this NEW root.'
Write-Output 'Only runtime\run and runtime\logs additionally grant service Modify. Code/config remain read-only to service.'
Write-Output 'Terminal profile, Python base installation and terminal executable permissions are NOT changed. No service is registered or started.'
if (-not $ApplyPermissionPlan) { return }
$admin = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'An elevated administrator must apply the reviewed permission plan.' }
if (-not $PSCmdlet.ShouldProcess($InstallRoot, 'Create dedicated service directories with the displayed exact ACL plan')) { return }
New-Item -ItemType Directory -Path $InstallRoot -ErrorAction Stop | Out-Null
# Set the new root ACL in one operation before creating any sensitive descendants.
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
foreach ($entry in @(@('S-1-5-18', 'FullControl'), @('S-1-5-32-544', 'FullControl'), @($sid, 'ReadAndExecute'))) {
    $principal = New-Object Security.Principal.SecurityIdentifier($entry[0])
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($principal, $entry[1], 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $InstallRoot -AclObject $acl
foreach ($folder in @('releases', 'config', 'runtime', 'runtime\run', 'runtime\logs')) {
    New-Item -ItemType Directory -Path (Join-Path $InstallRoot $folder) -ErrorAction Stop | Out-Null
}
foreach ($folder in @('runtime\run', 'runtime\logs')) {
    $path = Join-Path $InstallRoot $folder
    $runtimeAcl = Get-Acl -LiteralPath $path
    $principal = New-Object Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($principal, 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $runtimeAcl.AddAccessRule($rule)
    Set-Acl -LiteralPath $path -AclObject $runtimeAcl
}
Write-Output 'Created dedicated layout. No terminal profile, credentials or active service were created. Preserve this tree for diagnosis if later staging fails.'
