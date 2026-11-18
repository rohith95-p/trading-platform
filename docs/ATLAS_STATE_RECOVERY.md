# Atlas account-state reconciliation and recovery

Implemented18 November2026. This is an engineering protection and offline preparation workflow, not verification of current Atlas rules, profitability, a funded account, or real-money deployment.

## What changed

Startup no longer interprets missing, corrupt, wrong-phase or unbound legacy state as permission to start fresh. Persisted schema2 binds account login, server, program (`atlas_access`), phase, exact loaded-rule fingerprint and original initial balance. Peak equity, daily reference/high/start balance, protector strikes, payout-cycle days and last-trade timestamp are validated and retained. A phase transition requires an explicit separately reviewed account-state artifact, not an environment-variable reset.

Every state save disarms authorization until serialization, flush, filesystem sync and atomic replacement succeed. A runtime save failure raises, leaves authorization disabled and attempts to latch a persistent halt. An interrupted `.tmp` save prevents automatic startup from silently accepting an older looser state. No software can guarantee persistence on a completely failing storage device; retain authoritative broker/program history and investigate disk faults. This is not protection against a malicious administrator editing all evidence.

The scan-loop monitor and order path recheck account identity and persistence readiness. Missing account snapshots, missing Atlas runtime state or a previous save failure block new entries. Existing broker stops are not removed. No automatic liquidation or account-rule level was added by this change. Prior inherited generic risk-evaluation fail-closed repairs in `order_flow.py` are retained in the same commit.

**Operational consequence:** upgrading an established account that still has the old flat JSON will refuse the next startup until reviewed migration. No current running service was restarted and no actual account-state file was read, changed or migrated during this implementation. Do not clear a halt or delete a state file to bypass this refusal.

## Prepare migration offline

1. Stop new-order operation through a reviewed targeted maintenance process; preserve open-position protection. This runbook is not an instruction to stop the user's current service remotely.
2. Preserve the original state and any pending `.tmp`, existing account-bound state, journal and relevant program/dashboard records. Never overwrite these with a blank `AtlasState.new(current_balance)`.
3. Obtain authoritative **original initial capital**, all-time relevant equity peak, current daily anchor/high/start balance, phase, strike history, payout-cycle daily results and last trade time. Reconcile missing monitoring intervals against broker/program evidence. Current balance alone cannot recover these values.
4. Write a separate `reviewed_state.json` containing the complete `AtlasState.to_json()` field schema. The dates must be real UTC dates and timestamps; JSON numeric fields must be finite. The tool does not contact Atlas or prove the truth of these supplied values.
5. Run the preparation module with the exact intended account identity and phase. Use an offline output path that does not exist. Example with placeholders:

```powershell
.\venv\Scripts\python.exe -m scripts.reconcile_atlas_state `
  --source <preserved-legacy-state.json> `
  --reviewed-state <reviewed_state.json> `
  --output <new-offline-prepared-state.json> `
  --account-login <expected-login> --account-server <expected-server> `
  --phase evaluation `
  --review-note "Reconciled original capital, equity peaks, daily anchors, strikes and payout history against authoritative records"
```

The tool never installs the output at `logs/atlas_state.json` and rejects that destination. It preserves its source and will not overwrite existing outputs. Readable source capital/phase cannot change; recorded peaks and strikes cannot decrease; same-day risk anchors cannot loosen; payout-cycle days and last-trade history cannot be erased. Source and reviewed-input hashes plus the operator's explicit review note are saved in the artifact.

A genuinely new account uses `--new-account` and no `--source`, still requiring complete reviewed values and a review note. The tool never guesses that an account is new. A missing/corrupt source additionally requires `--recover-unreadable-source` with a source path and authoritative reviewed replacement; that flag explicitly records unavailable original evidence and does not make the replacement independently verified. A source bound to a different account/program/phase/rule set cannot be silently adopted through this recovery flag.

## Installation and verification remain manual and explicit

The separate prepared artifact must be reviewed against the intended account and exact rule configuration before any production installation. Preserve all originals, determine the correct account phase and investigate the failure that produced missing/corrupt state. Deal with a pending `.tmp` as evidence, not disposable clutter. Never reduce the known higher peak to the older committed file's peak merely to make startup pass.

This work provides no automated state installation, funded-account switch, live service restart, halt clearing or order submission. The account-specific rule conflicts described in `ATLAS_RULES_VERIFICATION.md` remain separate blockers. Do not interpret successful migration as a profitable-strategy certificate or Atlas approval.

## Validation

Tests use temporary state paths and synthetic account/terminal objects. They cover round-trip history, wrong account/server/program/phase/rule identity, legacy/missing/corrupt documents, invalid numeric history, failed atomic replacement, invalid-save latching, interrupted pending saves, offline preservation and refusal to erase history, actual order-path refusal, and unchanged risk-floor/strike/profit-day state across a synthetic restart. Frozen strategy/configuration tests remain unchanged in their numeric assertions. Final command/count and release commit are recorded in `FINALIZATION_STATUS.md`.
