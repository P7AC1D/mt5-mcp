# Native Windows SCM service

This implementation supplies a real `SERVICE_WIN32_OWN_PROCESS` service named
`MT5-MCP`, with Automatic boot startup and SCM failure recovery. It uses the
locked pywin32 dependency and the release's absolute Python interpreter, not a
logon task, shell loop, LocalSystem wrapper, downloaded service wrapper, or
automatic desktop logon. **The code/tests do not establish that MT5 works in
Session 0 on your installation.** Do not start it until profile, identity, client
compatibility and the maintenance boundary are reviewed.

## Identity and directory approval

The proposed identity is the dedicated virtual account `NT SERVICE\MT5-MCP`.
Windows manages it without a user-supplied Windows password. Registration requires
an elevated administrator. The scripts do not elevate themselves, change local
security policy, create a conventional Windows user, or request credentials.

Use a NEW dedicated directory such as `C:\ProgramData\MT5-MCP-Service`.
`New-Mt5ServiceLayout.ps1` defaults to displaying a permission plan and changes
nothing without `-ApplyPermissionPlan`. It refuses existing directories and
locations outside ProgramData. If approved, its exact plan is:

| Location | SYSTEM / Administrators | Service identity |
| --- | --- | --- |
| New installation root and descendants | Full control | Read/execute |
| `runtime\run`, `runtime\logs` only | Full control | Modify |
| Code, config and credentials | Full control | Read/execute (no write) |

It disables parent ACL inheritance only on that new root. It never recursively
re-ACLs an existing tree, grants access to Warren's profile, copies credential
stores, or changes Python/MT5 installation permissions. Review inherited ACLs on
every input location and the base interpreter/DLLs. `-WhatIf` is supported.
Do not give the service write access to its executable code or configuration.
If permissions cannot be provisioned as reviewed, stop; do not use LocalSystem.

The terminal needs its own approved service-identity profile/data location and
broker configuration. The application currently uses normal MT5 initialization,
not portable mode. Do not assume that the interactive user's terminal profile is
available to a different identity. Have the operator explicitly provision the
intended account using an approved secure process; never copy saved credential
databases or put passwords/tokens in commands, Git or chat. Do not change trading
settings as part of service installation. If a separate terminal installation
or permission changes are required, approve those exact changes separately.

MetaQuotes documents that `initialize()` can launch the terminal and use saved
account credentials, so even the first connection can have process/profile
side effects. It is not a side-effect-free Session 0 test. A service that only
proxies to a logged-in desktop worker would not meet boot-before-login availability.

## Stage and review (elevated administrator, after permission approval)

Adapt the source/release paths to the reviewed commit. No command here starts MT5.
Execute one step at a time and stop on any failure.
On the inspected machine, PowerShell 7 permits these scripts; Windows PowerShell
5.1 script execution is restricted. Use the already permitted PowerShell 7 in an
elevated administrator window. No execution-policy bypass or policy change is
needed or performed. The service itself launches Python directly, not PowerShell.

```powershell
$source = 'C:\Users\Warren\Documents\Codex\2026-10-10\task\mt5-service'
$root = 'C:\ProgramData\MT5-MCP-Service'
$releaseName = 'scm-candidate-01'
$uv = 'C:\Users\Warren\Documents\Codex\2026-10-10\task\deployment-tools\bin\uv.exe'
& "$source\scripts\windows\New-Mt5ServiceLayout.ps1" -InstallRoot $root
# Only after approving the displayed identity/ACL plan:
& "$source\scripts\windows\New-Mt5ServiceLayout.ps1" -InstallRoot $root -ApplyPermissionPlan
& "$source\scripts\windows\Stage-Mt5Release.ps1" -SourcePath $source -InstallRoot $root `
  -ReleaseName $releaseName -PythonPath 'C:\Python314\python.exe' -UvPath $uv
$python = "$root\releases\$releaseName\.venv\Scripts\python.exe"
```

The stage script also creates legacy `logs`/`run` folders at the root; the native
service does not use them. Service runtime state stays in `runtime\run`/`logs`.
Do not use `Set-Mt5Release.ps1`, `Register-Mt5Task.ps1` or `Start-Mt5Server.ps1`
for this SCM deployment. The service uses its own explicit `service.json` and
absolute interpreter, with no mutable pointer, PATH lookup or current-directory
dependence. `-I` isolates Python from user site packages/PYTHONPATH.

Create `$root\config\service.json` under the protected ACL, with no secret values:

```json
{
  "schema_version": 1,
  "env_file": "C:\\ProgramData\\MT5-MCP-Service\\config\\server.env",
  "terminal_path": "C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe",
  "runtime_root": "C:\\ProgramData\\MT5-MCP-Service\\runtime",
  "host": "127.0.0.1",
  "port": 8000
}
```

The terminal path is an example, not permission to start another instance of the
currently active terminal. Approve its service profile/process behavior first.
Create `server.env` via the approved secure local provisioning flow. It must set
`MT5_EXPECTED_LOGIN` and `MT5_EXPECTED_SERVER` to the intended account. Automatic
account switching must remain disabled. Optional explicit broker credentials
must be entered securely by the operator, not discovered/copied by deployment.
Standard settings precedence applies: machine/service process environment can
override the env file; inspect that environment safely as part of acceptance.

For remote clients, explicitly choose the original binding and allowed
hosts/origins and provision the required `MT5_HTTP_TOKEN` on both ends before
cutover. Use `MT5_LEGACY_SSE=true` when `/sse` compatibility is needed. Do not
remove the non-loopback authentication requirement, broaden the firewall, or
silently switch existing clients to localhost. Default JSON above is local only.
No auth token is generated by these scripts.

```powershell
$config = "$root\config\service.json"
& "$source\scripts\windows\Install-Mt5Service.ps1" -PythonPath $python -ConfigPath $config
# Prints exact identity/permission/recovery plan and validates configuration only.
# After explicit profile and permission review, register WITHOUT starting:
& "$source\scripts\windows\Install-Mt5Service.ps1" -PythonPath $python -ConfigPath $config `
  -Register -PermissionsReviewed -TerminalProfileProvisioned
sc.exe qc MT5-MCP
sc.exe qfailure MT5-MCP
sc.exe qfailureflag MT5-MCP
```

SCM configuration is Automatic; recovery restarts after 60, 120 and 300 seconds,
repeating the final interval, with failure count reset after 86400 seconds.
Nonzero reported exits also trigger recovery. **Once registered, the next boot
can start the service even if no manual start has occurred.** Complete validation
before any reboot; if blocked after registration, use `Set-Service MT5-MCP
-StartupType Disabled` until ready. No setup script performs a reboot/start.

The installer refuses an existing service instead of overwriting it. If initial
registration fails partway through, it attempts to remove only the newly created
registration and reports if cleanup failed. Check SCM state after any error.

## Coordinated start, read-only acceptance and recovery

First pause/drain the existing consumers, reconcile any uncertain operations and
stop only the identified old MCP process using its supported graceful mechanism.
Verify its exit and that no other bridge controls the same terminal. Existing
desktop MT5 must not be killed, logged out or moved to another account as an
implicit step. Coordinate any necessary terminal transition separately.

Then explicitly run `Start-Service MT5-MCP` and inspect:

1. SCM identity, Automatic start/recovery settings, process ID, interpreter and
   Session 0. Inspect the terminal's separate process/session/profile too.
2. `/healthz` and authenticated `/readyz`; SCM RUNNING alone proves only that the
   HTTP application started, not current broker readiness. Securely supply the
   bearer header in memory, never in a command line or transcript.
3. Read-only MCP terminal/account identity and already-visible market data;
   concurrent reads over both required transports. Confirm the expected account
   pins, original client endpoint and that no account switch happened.
4. A graceful `Stop-Service MT5-MCP`, proving the interpreter exits and the lock
   can be reacquired; then `Start-Service MT5-MCP` and repeat readiness.
5. On an explicitly approved demo/idle window only, simulate an ordinary process
   failure of the verified service PID and observe SCM's delayed restart. Never
   kill a process during a potentially mutating call, target terminal64, or replay
   orders. A native hang is not an ordinary crash and must not be force-recovered.
6. Boot without user logon requires a separately approved reboot test; it remains
   unverified until actually observed. The scripts never enable autologon.

Startup failures return a nonzero SCM result. Uvicorn stop closes the listener and
drains protocol work, then the existing application lifespan drains the exclusive
terminal owner and releases its lock. The service does not cancel the owner,
issue concurrent native shutdown, delete locks, truncate the journal or replay
operations. State/log files are stable across application releases.

If native shutdown is uncertain, the application retains the lock and the host
remains **STOP_PENDING**, advancing SCM checkpoints. It deliberately does not
exit to provoke recovery while a native call might still be running. Inspect
protected logs and reconcile before any manual intervention. Windows shutdown
deadlines can still terminate services; this code does not change system policy
or guarantee completion of an in-flight operation during OS shutdown.

Logs rotate at 5 MB with five backups in `runtime\logs\server.log`. Service-host
failures also send a sanitized exception type to the Windows Application event
log. Configuration values/credentials are not sent there. Readiness failures do
not automatically restart the process: network outages and uncertain native
work need diagnosis, not blind restart. SCM recovery restarts processes; it does
not prove a broker operation failed or roll it back.

## Stop, upgrade and rollback

Before changing service code/config, capture `sc.exe qc`, recovery settings, the
exact interpreter path and a protected copy of the configuration. Stage the new
release separately; do not modify an active environment. Keep the prior release.

After draining clients, temporarily set startup to Disabled to prevent boot races,
request a graceful stop, and verify Stopped plus actual PID exit. If it remains
STOP_PENDING, stop the upgrade: do not delete registrations/locks or kill MT5.

```powershell
Set-Service MT5-MCP -StartupType Disabled
Stop-Service MT5-MCP
Get-Service MT5-MCP
& "$source\scripts\windows\Remove-Mt5Service.ps1" -ConfigPath $config
# Registration only is removed. Files, profile, journal and logs are retained.
# Register the newly staged absolute interpreter (or the preserved prior one):
& "$source\scripts\windows\Install-Mt5Service.ps1" -PythonPath $python -ConfigPath $config `
  -Register -PermissionsReviewed -TerminalProfileProvisioned
# Explicitly start only after review and repeat acceptance checks.
```

Code rollback must retain the same compatible runtime journal/configuration and
account pins; never roll back the journal alongside code. Do not restore the old
Startup shortcut while an SCM service could also start. Do not restore any
shortcut pointing at changed source with incompatible dependencies.

## Evidence and limits

Lifecycle tests mock SCM and MT5. The real Windows parser/import checks do not
register a service or initialize a terminal. Session 0, broker connectivity,
failure restart and boot-before-login remain deployment acceptance tests.

- [Microsoft: services and Session 0](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services)
- [Microsoft: virtual service accounts](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-service-accounts)
- [Microsoft: failure actions](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_failure_actionsw)
- [Microsoft: non-crash failure actions](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_failure_actions_flag)
- [MetaQuotes: initialize behavior](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
