# Windows deployment and recovery

These scripts prepare a single-user MT5 MCP HTTP installation with immutable,
versioned application directories and shared runtime state. They are deployment
artifacts, not evidence that a Windows terminal has been tested or deployed.
Run deployment only in an explicitly approved Windows execution environment.
Nothing in the staging or health-check scripts places orders.

## Supported operating model

- Use 64-bit Windows, a supported 64-bit Python 3.11+ already installed from an official
  source, and an already installed `uv`. The checked-in `uv.lock` must match
  `pyproject.toml`; staging refuses to regenerate the lock.
- Install/open the intended MetaTrader 5 terminal yourself. Run the MCP launcher
  as that same Windows user in the same interactive desktop session. Verify the
  terminal's broker, account, and demo/live status yourself before enabling clients.
- Task Scheduler starts the launcher **at that user's logon**, with an interactive
  token and limited privileges. It retries a nonzero process exit up to ten times,
  one minute apart. `IgnoreNew` suppresses overlapping task triggers. The launcher
  holds an exclusive file handle; the application additionally holds a runtime lock.
- This is **not boot-before-login availability**. After a reboot the user must log
  on. Signing out ends the usable interactive session. A locked desktop can retain
  a logged-on session, but validate your actual terminal and broker behavior.
  Normal Windows sleep/battery policies still apply and can interrupt availability.
  No automatic logon, stored Windows password, service account, firewall rule,
  execution-policy bypass, or network/security setting change is configured.
- Binding is fixed to `127.0.0.1`. The client endpoint is
  `http://127.0.0.1:8000/mcp` by default (Streamable HTTP). `/sse` is not the new
  endpoint. Remote exposure requires a separate security and authorization design;
  these scripts do not publish the trading server on the LAN or internet.

Microsoft documents [interactive task principals](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal)
and [restart/multiple-instance settings](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset).
The resulting task must be inspected and tested on the target Windows installation.

## Layout

Use an operator-controlled local NTFS directory, outside the source checkout. Do
not place it on a network share or in a location writable by unrelated users. The
scripts do not change ACLs; review existing access before putting credentials or
account records there. Example paths below are placeholders to adapt locally.

```text
C:\Users\Alice\AppData\Local\MT5-MCP\
  current.json                    active release and absolute configuration paths
  previous.json                   preceding activation, for explicit rollback
  config\server.env               user-managed configuration, outside releases
  logs\server.log                 application rotating log
  logs\launcher.log[.1-.3]         launcher log, 1 MiB rotation threshold
  run\launcher.lock               launcher/activation gate (held open)
  run\server.lock                 application runtime lock (shared across releases)
  run\orders.jsonl                durable order journal (shared across releases)
  releases\2026-10-09-a\
    release.json                  written only after successful staging
    pyproject.toml
    uv.lock
    .venv\Scripts\python.exe      release-specific absolute interpreter
    src\mcp_server_mt5\
    scripts\windows\
    docs\windows-deployment.md
```

Do not delete a lock file to “unlock” a live process. The open OS handle is the
lock; a leftover file after a crash is harmless. Do not erase or roll back the
order journal during a code rollback. Back up the journal only with an
application-supported method or while the application is stopped. Read the
application's journal migration requirements before moving to older code.

## First installation

Use a normal PowerShell session belonging to the MT5 desktop user. Follow the
organization's script-signing/execution policy; no command below bypasses it.
The script parameters are absolute paths to keep startup independent of PATH,
the shell profile, or Task Scheduler's default working directory.

1. Review the source and its lockfile. Copy it to the Windows machine through the
   approved deployment process. Install prerequisites separately if necessary.
2. Manually create `config\server.env` in your installation root. It can contain
   non-secret settings only when using the terminal's existing logged-in account.
   Do not copy the example's placeholder credentials into a live configuration.
   Keep real credentials out of chat, command-line arguments, Git, and logs. If
   credentials are required, enter them locally through an approved secure flow.
3. Stage the reviewed source with locked dependencies:

```powershell
$source = 'C:\Code\mt5-mcp'
$root = 'C:\Users\Alice\AppData\Local\MT5-MCP'
$terminal = 'C:\Program Files\MetaTrader 5\terminal64.exe'
$python = 'C:\Users\Alice\AppData\Local\Programs\Python\Python312\python.exe'
$uv = 'C:\Users\Alice\.local\bin\uv.exe'

& "$source\scripts\windows\Stage-Mt5Release.ps1" `
    -SourcePath $source -InstallRoot $root -ReleaseName '2026-10-09-a' `
    -PythonPath $python -UvPath $uv
```

Staging copies application/deployment files, excluding `.env`, Git history, and
virtual environments. `uv sync --locked --no-dev --no-editable` installs the
locked runtime into the final release directory; it does not download a managed
Python. The interpreter import/64-bit check does not initialize MT5. A failed
stage has no `release.json` and cannot be activated. Leave it for diagnosis or
remove that incomplete directory deliberately; do not retry by overwriting it.
Virtual environments contain absolute paths: **do not move a staged release**.

4. Activate only after the env file and intended terminal path exist:

```powershell
& "$source\scripts\windows\Set-Mt5Release.ps1" `
    -InstallRoot $root -ReleaseName '2026-10-09-a' `
    -EnvFile "$root\config\server.env" -Mt5Path $terminal -Port 8000
```

Activation is an atomic pointer replacement and preserves the former pointer as
`previous.json`. It acquires both locks and refuses to switch under a live
launcher/application. It does not start the terminal or server.

5. Register the startup definition and inspect it:

```powershell
& "$source\scripts\windows\Register-Mt5Task.ps1" -InstallRoot $root
Get-ScheduledTask -TaskName 'MT5-MCP' | Format-List TaskName, State, Principal, Actions, Settings
```

Registration uses the current user, not an arbitrary account or `SYSTEM`. It
requires no Windows password and does not start the task immediately. If local
policy denies registration, ask the administrator for the narrow supported setup;
do not work around the policy by elevating or changing security settings.

6. With the intended terminal/account reviewed, explicitly start and check:

```powershell
Start-ScheduledTask -TaskName 'MT5-MCP'
& "$source\scripts\windows\Test-Mt5Health.ps1" -InstallRoot $root -WaitSeconds 60
Get-ScheduledTaskInfo -TaskName 'MT5-MCP'
```

The launcher runs the release's absolute `.venv\Scripts\python.exe` in the release
working directory with `-m mcp_server_mt5 --transport http --host 127.0.0.1`, the
configured port, and explicit `--env-file` / `--mt5-path`. It sets absolute
`MT5_LOG_FILE`, `MT5_LOCK_FILE`, and `MT5_JOURNAL_FILE` paths in the child environment;
keep those settings consistent for any separately launched process. It stays in
the foreground, returning the Python exit code so Task Scheduler can recover
ordinary crashes.

For an initial foreground diagnosis, run `Start-Mt5Server.ps1 -InstallRoot $root`
instead of starting the task. Stop it before testing scheduled startup. Never
run a second ad hoc interpreter with a different runtime lock against the same
terminal. Multiple installations also need deliberate terminal/account isolation;
per-installation locks cannot prevent a differently configured installation.

## Health, logs, and operational acceptance

If `MT5_HTTP_TOKEN` is configured, `/readyz` requires that bearer token. The health
script accepts an existing `MT5_HTTP_TOKEN` process environment variable or a
`SecureString` parameter. It does not read/dump the configuration file or accept
plaintext token command-line parameters. For a locally entered token:

```powershell
$token = Read-Host 'Configured HTTP bearer token' -AsSecureString
& "$source\scripts\windows\Test-Mt5Health.ps1" -InstallRoot $root -HttpToken $token -WaitSeconds 60
$token.Dispose()
Remove-Variable token
```

The header is sent only to the loopback probe URL, and redirects are refused.
A 401/403 is an authentication failure, not evidence that MT5 is disconnected.
The HTTP library necessarily holds the bearer header in process memory during
the requests; neither the header nor response bodies are written by this script.

`Test-Mt5Health.ps1` issues GET requests only to `/healthz` and `/readyz`, requires
HTTP 200 JSON responses from both, and exits `0` on success or `1` on failure. It
never calls an MCP tool, submits an order, changes the account, restarts a process,
or repairs the terminal. `-WaitSeconds` bounds the retry window; the last two
requests can extend it by up to twice `-TimeoutSeconds`. This is a connectivity
and readiness check, not identity verification, a trade test, or proof that a
previous order was/was not executed.

- `/healthz`: server liveness. A listening port alone is insufficient.
- `/readyz`: current application/MT5 readiness. Inspect logs if not ready.
- `logs\server.log`: application diagnostics and configured rotating backups.
  The launcher does not redirect stdout into an unbounded file. Startup errors
  outside application logging are reported in `logs\launcher.log` where possible.
- `Get-ScheduledTaskInfo`: task last run/result. A running task with an unready
  application requires investigation; automatic restart-on-failure reacts to
  process exits, not a health endpoint, network outage, or native-call hang.

Run the read-only native parser check before deployment (it does not load the
scripts or interact with MT5/Task Scheduler):

```powershell
& "$source\scripts\windows\Test-ScriptSyntax.ps1"
```

Before relying on this installation, test on the Windows target with a demo
account: normal start, no duplicate process from repeated starts, an ordinary
crash/restart, log rotation, broker connectivity recovery, stopping, reboot plus
manual logon, and upgrade/rollback. Check the process's exact interpreter,
working directory, terminal selection, and shared journal location. Do not
simulate a crash during any real order operation. Mock/unit tests in a Linux
cloud workspace do not validate MT5's Windows session integration.

## Upgrade, rollback, and recovery

A new release can be staged while the old one is running. Use a unique release
name and leave at least one known-good complete release on disk. Before changing
the active version, coordinate an interruption with clients and ensure no trading
operation is in flight. Stopping a process cannot undo a submitted order.

```powershell
# Stage the new reviewed checkout first, using the same Stage command and a new name.
# Prevent a logon/retry trigger racing the maintenance window, then stop the task.
Disable-ScheduledTask -TaskName 'MT5-MCP'
Stop-ScheduledTask -TaskName 'MT5-MCP'
Get-ScheduledTask -TaskName 'MT5-MCP' | Select-Object TaskName, State

& "$source\scripts\windows\Set-Mt5Release.ps1" `
    -InstallRoot $root -ReleaseName '2026-10-10-a' `
    -EnvFile "$root\config\server.env" -Mt5Path $terminal -Port 8000
& "$source\scripts\windows\Register-Mt5Task.ps1" -InstallRoot $root -Replace
Enable-ScheduledTask -TaskName 'MT5-MCP'
Start-ScheduledTask -TaskName 'MT5-MCP'
& "$source\scripts\windows\Test-Mt5Health.ps1" -InstallRoot $root -WaitSeconds 60
```

Execute the steps interactively and stop at any error; do not blindly paste the
entire maintenance block and continue after a failure. Confirm the old Python
process actually exited. Locks refuse activation if it did not. Task stop can be
abrupt; prefer the application's supported graceful stop where available. If the
launcher was terminated but its Python child survived, inspect that exact
executable, command line, user, and process ID before explicitly stopping it.
Never kill every `python.exe`, and do not delete runtime locks to get past it.

If the new version fails, after stopping it as above, restore the preceding
configuration explicitly:

```powershell
& "$source\scripts\windows\Set-Mt5Release.ps1" -InstallRoot $root -Previous
& "$source\scripts\windows\Register-Mt5Task.ps1" -InstallRoot $root -Replace
Enable-ScheduledTask -TaskName 'MT5-MCP'
Start-ScheduledTask -TaskName 'MT5-MCP'
& "$source\scripts\windows\Test-Mt5Health.ps1" -InstallRoot $root -WaitSeconds 60
```

`-Previous` swaps the active and prior configurations, permitting a deliberate
return after diagnosis. It does not restore old environment-file contents,
terminal/account settings, or journal data. Preserve compatible configuration
and journal schema across releases. Do not delete a release that is active,
previous, or still referenced by the scheduled task's launcher path. Re-register
on each activation so the task uses the selected release's reviewed launcher.

For failures, first inspect task result, logs, terminal/account status, existing
processes, paths, port conflicts, and readiness. A native call that remains hung
may mark the server unready while it continues holding the runtime lock. Do not
spawn a replacement or replay uncertain orders. Reconcile broker state using
read-only inspection and the durable journal before any separately authorized
recovery. A journal `started` record without a corresponding `completed` record is an
uncertain outcome. There is no automatic order replay. Readiness failure never
proves a trade failed or was rolled back.

## Why this is not a Windows service

The MT5 terminal is an interactive desktop application. Windows services normally
run in isolated Session 0; wrapping Python in NSSM, WinSW, or a service entry does
not establish that its MT5 terminal integration will work in that session.
See Microsoft's [interactive service guidance and Session 0 isolation](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services).

A true service deployment is a separate design and validation task. It needs a
supported terminal/session integration model, account/secret provisioning,
service identity and data-directory ownership, graceful-stop and hung-worker
recovery, shared journal and runtime-lock handling, logging, health observation,
and tested failure/reboot behavior. A service that brokers requests to an
interactive MT5 worker also needs authenticated local IPC and explicit behavior
when no user is logged in. Do not assume an interactive-token scheduled task can
be changed to `ServiceAccount`, `S4U`, or “run whether user is logged on or not”
without changing and validating that architecture.
