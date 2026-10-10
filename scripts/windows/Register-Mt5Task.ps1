#Requires -Version 5.1
#Requires -Modules ScheduledTasks
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$InstallRoot,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')][string]$TaskName = 'MT5-MCP',
    [switch]$Replace
)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-Mt5Windows
$InstallRoot = Get-Mt5AbsolutePath $InstallRoot
$config = Read-Mt5Config $InstallRoot
$release = Get-Mt5ReleasePath $InstallRoot $config.releaseName
$launcher = Join-Path $release 'scripts\windows\Start-Mt5Server.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Launcher is missing: $launcher" }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$user = $identity.Name
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$description = "MT5 MCP interactive logon launcher; installation: $InstallRoot"
$existing = Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    if (-not $Replace) { throw 'The task already exists. Review it first, then use -Replace to update this installation task.' }
    if ($existing.Description -ne $description) { throw 'Refusing to replace a task belonging to a different installation.' }
    if ($existing.State -eq 'Running') { throw 'Stop the existing task before replacing its definition.' }
}
if (-not $PSCmdlet.ShouldProcess("$TaskName for $user", 'Register a limited-privilege, interactive logon task (does not start it)')) { return }
$arguments = '-NoLogo -NoProfile -NonInteractive -File ' + (ConvertTo-Mt5CommandArgument $launcher) + ' -InstallRoot ' + (ConvertTo-Mt5CommandArgument $InstallRoot)
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $release
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $description
Register-ScheduledTask -TaskName $TaskName -TaskPath '\' -InputObject $task -Force:$Replace | Out-Null
Write-Output "Registered $TaskName for $user. It runs only in that user's logged-on interactive session; no password was stored. Start it explicitly, or at that user's next logon."
