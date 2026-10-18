# Operations runbook — dead-man heartbeat, supervisor, halt latch, measurement-only (2026-10-18)

## What was added
| Piece | File | Purpose |
|---|---|---|
| External heartbeat | `src/core/ops.py` (`build_status`, `push_status`), wired in `main_loop._push_ops_heartbeat` | POSTs a status payload (commit, config fingerprint, quote age, positions, pending orders, daily P&L, rule state, account type) at most every 30 s, in a daemon thread (never blocks the loop) |
| Persistent halt latch | `src/core/ops.py` + `scripts/halt.py` | A halt lives in `logs/HALT_LATCH.json`. A crash/restart cannot clear it. Only `python -m scripts.halt clear --note "..."` does (note mandatory, latch archived). Corrupt latch file = still halted. |
| Latch triggers | `main_loop._execute_signal` | A `risk_rules` HARD HALT (peak-drawdown/monthly kill) now also sets the latch. Startup is refused while it is set. |
| Measurement-only mode | env `ULTRA_MEASURE_ONLY=1` | Bot scans, logs signals as "blocked: measurement-only mode", reconciles, heartbeats; sends **no orders**. Default of the supervisor. |
| Supervisor | `scripts/supervisor.py` | Starts/restarts the bot after a crash with backoff (5,10,20…300 s), refuses to start under halt latch or STOP file, crash-loop guard (5 crashes/10 min), rotating log (5 MB x 5), hung-process kill (heartbeat file > 5 min), sleep/resume detection, optional supervisor heartbeat. |
| Task installer | `scripts/install_supervisor_task.ps1` | Registers `UltraCoreSupervisor` (boot + logon, wake, restart-on-failure, battery OK). **Dry run by default**; `-Apply` registers; `-Trade` selects trade mode. Not applied by this change. |

## Set up the external dead-man alert (you do this once)
1. Create a free check at healthchecks.io (or run Uptime Kuma). Period **1 minute**, grace **3 minutes**.
2. Add your Telegram / email integration there. The alert fires when pings **stop** (PC asleep, crashed, offline) — nothing local can do that.
3. Put the ping URL in `.env.local` (never commit): `ULTRA_HEARTBEAT_URL=https://hc-ping.com/<uuid>` (bot) and optionally `ULTRA_SUPERVISOR_HEARTBEAT_URL=...` (second check for the supervisor).
4. A latched halt pings `<url>/fail` on healthchecks.io so it alerts immediately.
Note: on weekends `quote_age_s` is large because the market is closed; do not alert on quote age outside trading hours.

## Run
```
python -m scripts.supervisor            # measurement-only (recommended default)
python -m scripts.supervisor --trade    # allow orders (demo account)
powershell -ExecutionPolicy Bypass -File scripts\install_supervisor_task.ps1          # dry run
powershell -ExecutionPolicy Bypass -File scripts\install_supervisor_task.ps1 -Apply   # register at boot/logon
python -m scripts.halt status | set --reason "..." | clear --note "..."
```
Disable the old `UltraCoreBot` task when you enable the supervisor so two launchers do not compete. Also set the PC to never sleep while plugged in (power settings are not changed by these scripts).

## Acceptance tests
| Test | Result 2026-10-18 |
|---|---|
| Bot starts under the supervisor, heartbeat payload received | **PASS** (payload: account=demo, commit, fingerprint, rule_state=MEASURE_ONLY) |
| Supervisor publishes its own heartbeat | **PASS** |
| Kill the bot process -> supervisor restarts it, heartbeats resume | **PASS** |
| Latch a halt, kill the bot -> not restarted ("not starting: halt latch set") | **PASS** |
| Clear the latch with a note -> restarts | **PASS** (latch archived) |
| Rotating log written | **PASS** |
| Unit tests (23, `tests/test_ops.py`): latch persistence, fail-closed corrupt file, clear needs note, measurement-only sends nothing, payload, POST to a real local endpoint, `/fail` routing, rate limit, supervisor decisions | **PASS** (268 tests total) |
| PC sleep -> external alert fires | **NOT TESTED** (needs the external service configured and a sleep) |
| Network disconnect -> stale-quote/heartbeat alerts | **NOT TESTED** |
| Friday flatten with pendings cancelled | **NOT TESTED** (bot does not use pending orders; positions flatten as before) |
| Reconciliation mismatch -> alert + entries blocked | **NOT IMPLEMENTED** |
The acceptance run used alerts disabled and a local heartbeat receiver; the test halt was cleared and archived.

## Not done yet (honest list)
- Heartbeat-silence **protective action** (cancel pendings/flatten) is not automated; the dead-man action is an alert to you.
- Daily-loss / order-reject-burst / reconciliation-mismatch alerts are not yet raised from the payload.
- Validation fingerprint still does not include code commit / engine version (the commit is in the heartbeat payload only); it does not block the measurement-only restart.
- `protect_profit.py` is not started by the supervisor (no positions in measurement-only mode).
- Telegram token revocation remains the owner's decision.

## Account scoping: strategy view vs account view (2026-10-18)
Allowlist: `config/ultra_magics.json` (every PORTFOLIO leg magic must be listed, or the bot refuses to start; a missing/invalid file also refuses).

| Uses OWN magics only (strategy view) | Uses EVERYTHING on the account (account view) |
|---|---|
| signals/entries, "one position at a time" count, trailing/break-even (`protect_profit`), kill-switch flatten, streak breakers, per-strategy P&L (`position_closed` logs `risk_scope=strategy`, `magic`) | daily loss, floating P&L, equity drawdown, symbol exposure cap, margin, halt state |

Foreign exposure rule (fail closed): if a non-Ultra-Core position exists on XAUUSDm, all new Ultra Core entries are blocked, a `FOREIGN EXPOSURE DETECTED` alert is sent (once per change of the ticket set) and logged with magic, ticket, volume, direction and floating P/L (`risk_scope=account`). Foreign positions are never closed or modified unless `ULTRA_ACCOUNT_WIDE_FLATTEN=1`. With orders enabled, startup is refused while foreign positions exist. `ULTRA_BLOCK_ON_FOREIGN=0` disables the block (not recommended).
Account ownership: until one account-level governor controls both systems, run Ultra Core on its own demo account or in measurement-only mode. The -$66.12 loss (magic 5150001) is not Ultra Core's; it is excluded from strategy metrics and included in account risk.
Not done: startup check that no *other* EA uses our magics (MT5 cannot tell which EA placed a deal); the running bot picks these changes up only on its next restart.
