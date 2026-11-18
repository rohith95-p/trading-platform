# Deployment readiness — 18 November 2026

## Current classification

**Research-capable local checkout; demo release not yet operationally certified; real-money readiness not established.** The older runbook describes an AWS Windows VPS/Exness rehearsal, not a newly verified deployment. No remote connection, MT5 initialization, broker order, Telegram notification, account purchase, service restart or production configuration mutation was performed in this readiness review.

A November22 deadline cannot turn a short prospective sample into proof of positive expectancy. Deliver tested software and explicit no-edge/abstention status if research does not qualify a strategy.

## Local code inspected

`.agents/AGENTS.md`, README, research decision/audit logs, `src/core/main_loop.py` startup, `atlas_bridge.py`, `risk_rules.py`, portions of `resilience.py`, `execution_handler.py` references, watchdog/startup/update scripts, CI workflow, requirements and test isolation. This is a bounded source review, not a full security certification or a check of currently running services. Source-backed defects are not assumed repaired unless another finalization artifact cites the actual change and tests.

## Release blockers

| Priority | Observation | Evidence / required closure |
|---|---|---|
| P0 | No qualified trading edge from recovered studies | `research/STRATEGY_VALIDATION_REPORT.md`; final research policy is abstain unless a new candidate passes |
| P0 | Established-account state requires reviewed migration before upgrading | Fresh-reset defect repaired: schema2 account/server/program/phase/rule/capital binding, durable-save authorization and pending-write refusal. Existing legacy/corrupt/missing histories intentionally cannot restart until offline authoritative reconciliation. See `ATLAS_STATE_RECOVERY.md`; no actual account migrated |
| P0 | Broker/account-specific Atlas rules and XAUUSD contract unverified | User is researching before buying; current official-page review cannot substitute for signed account terms and broker probe |
| P0 | No independently reconciled real-tick / demo execution record for final candidate | Need signal→intent→request→order→deal→position journal, unknown/partial fill recovery and equity/cost reconciliation |
| P1 | Validation ledger can be bypassed with `ULTRA_ALLOW_UNVALIDATED=1` | Startup source; a release must explicitly reject/record this override and require a validated release identity |
| P1 | Existing demo switch relaxes daily and some streak/hard controls | `risk_rules.py`; demo does not imply same risk behavior or a no-order mode |
| P1 | Broker profile differences warn and continue | Startup source; define which contract, clock, account or margin discrepancies must prevent orders |
| P1 | Release activation and runtime rollback remain unverified | Unsafe latest-master/all-Python updater was replaced with pinned, hash-verified prepare-only workflow. No production stop/start/copy remains. A reviewed activation, account-state preservation and rollback drill are still required |
| P1 | Legacy runbook includes all-Python stop advice | Follow a reviewed targeted procedure. State-deletion advice has been superseded by `ATLAS_STATE_RECOVERY.md`; never reset account risk history |
| P1 | Watchdog heartbeat timeout is300 seconds | `scripts/watchdog.py`; heartbeat recovery is not independent quote-speed risk supervision; test stale/blocked-loop and network-loss behavior |
| P1 | Dependency/CI runtime compatibility not certified | CI says Python3.11 while current requirements contain newer pinned numpy/pandas/scipy; fresh clean installation must prove compatibility |
| P1 | Research files remain outside committed release | November11 source/data/results were untracked at recovery; committing old results now does not retroactively establish preregistration |
| P1 | Historical experiment provenance remains incomplete | Repaired `prereg_check.py` now rejects uncommitted/dirty evidence and uses Git ancestry. Current registry check:14 verified,3 explicitly weak,12 failed. Failures must be honestly classified, not retroactively relabeled |
| P2 | README foregrounds superseded selected-period PFs | Recovery/validation reports supersede those promotion claims; align documentation before distribution |

The execution-audit workstream owns backtesting fixes and additional defects in `BACKTEST_REALITY_AUDIT.md`. Do not infer that every P0 above belongs to the backtester or that a unit-test pass closes a live-account issue.

## Useful controls already present

Startup checks account connectivity, symbol, halt state, portfolio-owned magic numbers, recorded configuration and hedging mode; blocks foreign exposure by policy. `ULTRA_MEASURE_ONLY` is explicitly logged as no-order intent in startup and is checked in order flow. Durable halt state, deduplication, broker profile measurement, feed freshness/repair, attached broker stops and alert journaling provide a useful foundation. Their existence does not certify every fault path.

Test fixtures disable live alerts, redirect runtime state to temporary directories and suppress research trial-ledger writes for synthetic tests. Linux CI uses an MT5 stub when the native package is unavailable: this tests offline logic, not Windows terminal integration.

## Reproducible demo release sequence

1. Finish current offline tests and source/data audit; save exact commands, complete outputs and SHA in `FINALIZATION_STATUS.md`. Check `git diff --check` and verify production strategy/freeze settings unchanged.
2. Create a coherent experimental release from explicitly reviewed files. Preserve dirty local research as evidence; exclude secrets, unrelated files and provider data whose redistribution rights are unverified. Pin compatible interpreter and resolved dependencies; reproduce installation in a clean environment.
3. Prepare a dedicated Windows demo terminal/account and isolated runtime directory. Verify account type, login/server, hedging mode, symbol contract, quote decimals, UTC/server clock, minimum lot/step, stops/freeze levels, margin, commissions and swap. No real account should be reachable by this release.
4. Begin measurement-only with verified no-order enforcement. Validate event-calendar age/status, market-hour/DST interpretation, quote/bar freshness and signal parity. Capture a timestamped broker profile and configuration fingerprint without exposing secrets.
5. Test restart, corrupt state, stale quote, failed calendar, rejected/unknown/partial response, lost connection, duplicate submission, local write failure and watchdog recovery using mocks first; close all fail-open outcomes before order-enabled demo.
6. A qualified frozen candidate, if available, can then enter an explicitly isolated demo-only trial. Reconcile every request and deal, including gap stops, spread, latency, swaps and risk-floor movement. Keep the original production portfolio/settings untouched.
7. Record enough prospective observations to meet predeclared sample and uncertainty requirements. No sufficient sample means “not yet verified,” regardless of deadline. Account-rule simulation must use verified phase-specific terms and model evaluation→funded→eligible payout with residual equity.
8. Produce a pinned artifact, deployment/rollback manifest and targeted start/stop procedure. Verify task/service identity and restart without killing unrelated Python processes. Record observed demo status separately from prepared instructions.

These are execution prerequisites, not a claim they were completed. No automatic background monitoring was configured here.

## Safe offline commands

Run from the repository with its own virtual environment. These commands do not intentionally initialize MT5 or send notifications:

```powershell
.\venv\Scripts\python.exe -m pytest -m "not live" -q
.\venv\Scripts\python.exe -m pytest tests/test_live_freeze.py tests/test_config_integrity.py -q
.\venv\Scripts\python.exe -I scripts/validation/prereg_check.py
git diff --check
git status --short
```

The parent finalization workstream runs the full suite and reports the actual count. `prereg_check` now fails closed on uncommitted evidence; `--strict-weak` also rejects legacy same-commit records. A prior-ancestor result checks recorded introduction order, not the actual runtime or protocol compliance. Do not run the historical updater, broker probe, watchdog, halt-clear or live-loop commands merely because they appear in old documentation.

## Remaining external inputs

An actual accessible dedicated demo terminal and deployment host, broker-native demo fills/quotes, approved release identity, and exact account-specific prop-firm terms are not established by this local review. No paid historical futures data is available. Managed Linux research/cloud work does not automatically provide native Windows MT5 execution. Prepare offline research portability separately from Windows broker integration.

## Files produced by this review

- `research/PROJECT_RECOVERY_2026-11-18.md`
- `research/STRATEGY_VALIDATION_REPORT.md`
- `research/FINAL_STRATEGY_SPECIFICATION.md`
- `docs/DEPLOYMENT_READINESS.md`

No trading or production configuration was changed. Current operational status remains **unverified**, not “deployed successfully.”

## Demo release tooling completed in this workstream

`vps_update.ps1` now **prepares only**. It requires an exact40-character revision, a local GitHub revision archive and an independently supplied SHA256. It no longer fetches latest master, kills Python, overwrites the running checkout, installs dependencies into the live environment or starts the watchdog. Existing updater invocations without these mandatory inputs intentionally no longer deploy.

`scripts/demo_release.py` provides immutable staged extraction, per-file SHA256 manifests, code/config rollback snapshots, tamper verification and a read-only owned-process plan. Archive roots must match the pinned revision; traversal, symbolic links, duplicate/case-colliding files, excessive expanded size and incorrect checksums are rejected. Secrets filenames, runtime logs, environments and research datasets are excluded. This is an allowlisted code/config artifact, not a full research-data transfer or a secret-scanning certification. It performs no process termination, service control, broker action or release activation. Rollback code snapshots do not include account history: preserve and reconcile actual runtime state separately, never roll risk peaks back with code.

`scripts/demo_preflight.py` defaults to presence-only inspection, without loading `.env.local` or initializing MT5. An explicitly requested read-only diagnostic can verify the currently connected terminal against supplied demo login/server, hedging mode, valid XAUUSD contract fields and an empty dedicated account. Real/unknown/wrong accounts or failed exposure reads refuse. Its adapter exposes only permitted read calls and denies order methods. Passing this diagnostic does not activate a bot or authorize order-enabled deployment; time-sensitive spread/fill/news behavior is still unverified.

Actual local presence check in this workstream: project Python present, local settings file present, native MT5 package available. **No terminal connection was made, no account demo identity was verified, and VPS access was not established.** File/package presence is not evidence of a logged-in funded or demo account.

Offline validation:23 safety tests passed for release/archive integrity, no live overwrite, rollback-state exclusion, owned-process planning, demo identity and denied order API; the PowerShell updater parses successfully without execution. Parent checkpoint records the final full-suite count and commit.

Preparation examples (never activate or trade):

```powershell
# Presence only; reads no secrets and does not connect a terminal.
.\venv\Scripts\python.exe scripts/demo_preflight.py

# Preserve an immutable code/config rollback snapshot before any maintenance.
.\venv\Scripts\python.exe scripts/demo_release.py --snapshot-current before_demo_release
.\venv\Scripts\python.exe scripts/demo_release.py --verify-release release_staging/rollback_before_demo_release

# Use exact trusted revision/hash values in place of the placeholders.
powershell -NoProfile -File scripts/vps_update.ps1 -Revision <40-character-SHA> -ArchivePath <local-revision.zip> -ArchiveSha256 <64-character-SHA256>
```

Do not run a connected preflight merely to satisfy a deadline. An isolated terminal/account and explicit intended identity must be available first. Current package remains **prepared, not deployed**, and the selected strategy remains unqualified unless separate final evidence changes that verdict.

## Atlas state protection completed

Account-bound schema2 persistence and the order/monitor readiness guard now refuse missing, corrupt, legacy unbound, mismatched and unsuccessfully saved state. No original strategy, lot, session, stop, target or rule level was changed. The inherited risk-evaluation exception refusal was preserved in `order_flow.py`.89 focused state/halt/glue/freeze/config tests passed. The read-only/offline migration tool prepares a separate reviewed artifact and refuses to overwrite runtime state; it does not verify the truth of supplied dashboard/history values. Established deployments require explicit migration before their next startup. No actual runtime file was migrated and no running service was changed. Full procedure and remaining limitations: `ATLAS_STATE_RECOVERY.md`.

## Historical Access lifecycle replay executed

The pre-registered real-engine/provisional-ledger run on the already explored July6–October29 2026 window stopped **indeterminate at July6 20:45 UTC**: an existing open position meets a block with13/15 M1 observations (20:58/20:59 absent). It records0 realized closes,$5,000 cash balance and last supported modeled net-liquidation equity$5,046.844. Evaluation completion, funded transition and payout opportunities therefore remain unverified; actual payments are zero. No missing quotes, liquidation fills or continued account survival were invented. See `../research/results/access_lifecycle_2026-11-18/REPORT.md` for exact protocol, source hashes, trace and data-recovery requirement.43 focused lifecycle/provisional-rule tests pass; no production deployment occurred.
