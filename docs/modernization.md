# 0.2 migration, concurrency and compatibility

## Deliberate compatibility changes

- Python 3.11+; official `mcp==2.3.0` and Windows `MetaTrader5==5.0.6231`.
  Use the checked-in `uv.lock` with `uv sync --locked`. Linux can run the complete
  fake-terminal suite; native MT5 remains Windows x86-64 only.
- `/mcp` is the primary Streamable HTTP endpoint. The SDK handles MCP
  2026-07-28 envelopes and older protocol negotiation. SSE responses are retained
  so request cancellation can propagate. The server does not implement its own
  protocol/version parser.
- Legacy `/sse` and `/messages/` are available only with `MT5_LEGACY_SSE=true`
  or `--legacy-sse`. They share the same terminal owner and lifecycle with `/mcp`.
  SSE clients are bounded by `MT5_MAX_SESSIONS` and a connection lifetime of
  `MT5_LEGACY_SSE_MAX_SECONDS` (default 300 seconds).
- HTTP binds to `127.0.0.1`, not every interface. Non-loopback binding requires
  `MT5_HTTP_TOKEN` and explicit `MT5_ALLOWED_HOSTS`. Allowed Host/Origin lists use
  JSON arrays. Configure allowed origins for browser clients, without disabling
  DNS-rebinding checks. Remote traffic requires TLS at a trusted reverse proxy.
  A preconfigured bearer token is a private-client option, not an OAuth server.
- `login` remains registered but requires `MT5_ALLOW_ACCOUNT_SWITCH=true`.
  Separate terminals per account are safer. Account and broker identity are
  pinned on initialization; optional `MT5_EXPECTED_LOGIN`/`MT5_EXPECTED_SERVER`
  fail startup when the wrong account is connected. A successful login must
  actually leave the requested account/broker active. Requests admitted before
  an account change fail rather than execute on the new account.

## Tool and resource contract

All 33 tool names, accepted parameter names and successful JSON text payloads
remain available. `get_orders` remains an alias. In addition:

- `structuredContent` contains the object result. Original array results
  (symbols, bars, ticks) use `structuredContent.result`; text remains the original
  JSON array. Output schemas describe the object envelope.
- Tool failures set `isError=true`. Native errors include `error`, `error_code`,
  `kind`, `operation_id` and `outcome_unknown`. Broker rejections preserve their
  failure payload but set `isError`; ambiguous timeout/connection return codes
  include an uncertainty warning. `check_order.valid=false` remains an ordinary
  successful check result, not a claim that a trade was submitted.
- Empty native tuples mean empty data. Native `None`/failure no longer means zero
  positions/orders/history. Consumers must distinguish failed reads from empty
  data and refuse decisions that depend on unavailable information.
- Unknown tools/invalid resource URIs are protocol errors. Four concrete resources
  are listed separately from two `{symbol}` templates. Resource matching is
  anchored and URL-decoded symbols are validated.
- Inputs follow the published JSON schemas, reject unknown properties/non-finite
  values, and enforce positive quantities and configured count/date limits.
  Naive ISO dates are consistently interpreted as UTC, never machine-local time.
  Large native results fail explicitly rather than silently truncate.

### Aurum compatibility

Aurum's inspected client uses a hand-written HTTP/SSE handshake with protocol
`2024-11-05`. It cannot use `/mcp` just by changing its URL. Enable legacy SSE
until its transport is upgraded. All observed Aurum tool names remain registered.

The unmodified inspected client was exercised against this server with a fake
terminal: `get_positions` and `get_orders` completed over `/sse`, with one native
initialization and one shutdown. No real terminal, account or trade was used.
This confirms the transport/text contract only. Aurum also needs client-side
fixes before live trading: send authentication headers, honor `isError` and
`outcome_unknown`, stop masking failed reads as empty/zero, and never retry a
trading mutation after dispatch. Read-only retries must be bounded and typed.
Those consumer changes are separate from this server repository.

## Ownership and cancellation

HTTP accepts concurrent clients. Complete terminal operations enter a bounded
FIFO queue, serviced by one dedicated thread. Initialization, account changes,
read-modify-write tools, the native call and `last_error`, and shutdown execute
on that same owner. Trading arguments/passwords are never written to the journal.

- Queued cancellation/deadline expiry prevents dispatch.
- Once dispatched, native work continues to completion even if the requester
  cancels or disconnects. Ownership is not released and the operation is not
  retried. Independent liveness requests remain responsive if the extension
  releases the GIL; GIL behavior is not guaranteed by MetaQuotes.
- The end-to-end deadline includes queue time. An active overdue job makes
  readiness false and rejects new work until it really finishes. A completed job
  cannot leave a permanent stale timeout flag.
- Shutdown atomically stops admission, rejects queued work, waits for the active
  call, and then shuts down the native connection. It never overlaps that call.
  If draining times out, an OS lock is retained for the process lifetime, even
  if the application object is garbage-collected. Restart requires confirming
  the old process exited and reconciling uncertain trades.
- One ASGI worker only. Multiple processes/accounts need separate terminals and
  lock paths. A lock cannot control unrelated applications or GUI users.
- MarketWatch selection and market-depth subscriptions remain terminal-global,
  not isolated per MCP client. Coordinate subscription changes between clients.

A dedicated thread is intentionally simpler than a subprocess bridge but cannot
kill a native hang or guarantee responsiveness if the native extension holds the
GIL. No automatic reconnect, hard-kill recovery or replay is implemented.

## Operation journal and recovery

`MT5_JOURNAL_FILE` defaults to `.runtime/operations.jsonl`. The Windows launcher
uses one shared path across releases. Before a mutating tool runs, its UUID,
operation name, timestamp and `started` state are appended and fsynced. Completion
and the resulting payload are appended afterward. A pre-dispatch journal write
failure prevents dispatch. Completion-journal failure is explicitly uncertain.

A `started` entry without `completed` is conservatively unresolved, even if a
validation/account check prevented dispatch. Review terminal order/deal history
and application records. A completed result may still contain a broker timeout,
connection failure or rejection; inspect it. Never infer that a new submission
is safe from the absence of a reply or a completed journal entry alone. The
journal is an audit aid, not broker-provided idempotency or distributed consensus.
Back it up, keep it private, and do not delete it during rollback.

Readiness is cached and refreshed every five seconds. Restore an externally
changed account or deliberately restart under the correct configuration. A
terminal process restart that invalidates the Python connection requires an
operator-controlled bridge restart; do not replay pending mutations.

## Acceptance and sources

Run `uv run --locked pytest`, `ruff check`, `ruff format --check`, and `pyright`.
The suite includes real SDK HTTP sessions with a fake terminal, both protocol
families, concurrent clients, legacy SSE, correct errors/templates, request limits,
authentication, Host/Origin protection, queue pressure, cancellations, overdue
recovery, shutdown races, account changes, and durable completion after cancellation.

Windows validation remains required: native import, terminal/path/account check,
read-only smoke requests, two clients, process crash/restart, logon, reboot after
login, lock/RDP disconnect, network loss and rollback. See the deployment guide.
Do not test by sending orders to a live account.

Official references checked October 9, 2026:

- [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
- [SDK v2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)
- [SDK migration](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/migration.md)
- [SDK cancellation](https://py.sdk.modelcontextprotocol.io/handlers/cancellation/)
- [MetaQuotes initialization](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
- [MetaQuotes order submission](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py)
- [Official MetaTrader5 package](https://pypi.org/project/metatrader5/)
