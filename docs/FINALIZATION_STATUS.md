# Finalization checkpoint — 18 November 2026

## Outcome

Substantial research and engineering execution completed; **no independently qualified profitable strategy selected**. Demo deployment not performed. Real-money readiness not established. Production strategy, risk settings and account configuration unchanged. November1 onward holdout outcomes unused. No terminal/broker orders, notifications, purchases, remote restarts or push to GitHub.

## Work completed and measured findings

- Recovered source-backed portfolio failure: PF0.900, -$1311.35 across2556 trades in reset2004–2022 eras; every leg negative. More attractive selected-period evidence is not independent confirmation.
- Inspected36 actual NPY/CSV files, recorded content hashes, timestamps, gaps, duplicate/missing fields, OHLC validity and spread provenance. All36 parse in the final inventory. Found441 inconsistent daily-proxy OHLC rows. Archive/Genesis spread fields are entirely zero; no free execution assumption.
- Committed a fixed market-discovery protocol, then computed six resolutions: M1 6,887,193; M5 100,000; M15 514,712; H1 126,553; H4 7,498; D1 7,074 observations. Exact adjacent returns exclude gaps. H1 derives from complete M15 groups. Coverage is unequal; no ranking of timeframes is certified.
- Evaluated18 fixed conditional summaries,999 monthly bootstrap draws, Bonferroni18, fixed eras and DST-aware local clock summaries. M1 absolute-return lag1=.3558 versus signed-return lag1=-.0224. Extreme M15 reference reversal averages.359bps before fees. Discovery is not independent confirmation.
- Economic hurdle screen: M1 reversal reference movement $0.01861/oz versus modeled friction $0.33479; M15 $0.05311 versus $0.32288. These are descriptive cost comparisons, **not scratch backtests**. Neither passes the declared candidate promotion gate. No candidate strategy test or holdout evaluation was fabricated.
- Reviewed10 primary literature/method records with reading-depth disclosure and all requested metadata. Current official Access pages differ from local production rules and contradict another official comparison page. Signed plan/account terms remain necessary.
- Implemented separate versioned experimental payout/event ledger with30 boundary tests: lifetime best-day consistency, payout timing, explicit approval/settlement, permanent Protector split effects, daily/trailing floors and missing-state refusal. No live rule replacement; no claim of full account simulation.
- Fixed execution assumptions: entry-minute protection, adverse gap stops, partial-minute coverage refusal, future-close interpolation refusal, experiment risk-constant isolation, opening-state chronology, next-scan daily-loss accounting and explicit balance-only equity diagnostics. Updated independent fill checker metadata and meaningful regression cases. Actual tick and broker parity remain unverified.
- Repaired preregistration checker to use Git ancestry and reject uncommitted/dirty evidence. Repository evidence audit now correctly fails:14 verified,3 weak,12 failed. Historical omissions are not retroactively repaired by committing after results.
- Added prominent README research status and a reproducible local source review/demo-preparation bundle builder. Package does not start, deploy or enable a bot, and excludes credentials and historical bars.

## Files and deliverables

1. research/GOLD_MARKET_ATLAS.md
2. research/DATA_FORENSICS_REPORT.md
3. research/GOLD_RESEARCH_LITERATURE.md
4. research/MARKET_EDGE_DISCOVERY.md
5. research/ORIGINAL_STRATEGY_RESEARCH.md
6. docs/BACKTEST_REALITY_AUDIT.md
7. research/STRATEGY_VALIDATION_REPORT.md
8. research/FINAL_STRATEGY_SPECIFICATION.md
9. docs/DEPLOYMENT_READINESS.md and docs/ATLAS_RULES_VERIFICATION.md
10. research/PROJECT_RECOVERY_2026-11-18.md and docs/FINALIZATION_STATUS_2026-11-18_SCOPE.md

Machine-readable numerical evidence, hashes, literature records, economic screen and verification outputs: research/results/finalization_2026-11-18/. New code: scripts/research/market_atlas.py, market_edge_discovery.py; src/research/access_rules_20261118.py; scripts/validation/build_finalization_bundle.py; prereg and engine/audit fixes listed in Git commits and execution report. Focused regression files cover market causality, payout rules, real Git provenance, protective fills and minute chronology.

## Tests and reproducibility

- `.\venv\Scripts\python.exe -m pytest -m "not live"`: **634 passed in28.39s**, exact output pytest.log in the results folder. Synthetic tests isolate runtime state and alerts; no live terminal certification implied.
- `.\venv\Scripts\python.exe -m scripts.research.market_atlas`: exit0;36 file inventories and six numerical studies completed. Earlier serialization failure and volatility-window correction are disclosed in the committed protocol amendment. Final script hash matches numerical artifact.
- `.\venv\Scripts\python.exe -m scripts.research.market_edge_discovery`: exit0; final script hash matches its artifact.
- `.\venv\Scripts\python.exe scripts/validation/prereg_check.py --strict-weak`: exit1 as required by actual evidence gaps;14 verified,3 weak,12 failed. Full log provenance_check.log saved. Do not call this gate passed.
- New market, economic-screen and bundle scripts compile. `git diff --check` exits0 (existing line-ending warnings only). Review-bundle builder performs CRC and individual content-hash verification when run.

## Commits and existing working tree

Implementation commits include45e2ba6 (discovery prereg),4ec99a3 (execution regression contract),b83ff9b (literature/rules),0c80ebc (disclosed volatility-window clarification),37709b2 (execution fixes),dc76e01 (experimental ledger),c9efc0e (provenance/recovery),a4557c9 and0b235ad (causal chronology),dce8073 and0ce4a01 (immediate loss/equity labels). Latest execution implementation: **0ce4a01**. The final atlas/source/checkpoint commits follow; obtain exact current revision with `git log -1 --oneline` and the generated bundle manifest rather than a self-referential commit hash in this document.

Preexisting modifications in full_metric_suite.py, data.py, metrics.py, report.py, order_flow.py and test_dedup_regression.py, plus older untracked November11 research, were preserved. Do not claim this is a clean checkout or retroactively pre-registered history. Engine/auditor commits deliberately include disclosed prerequisite earlier pending changes. No broad staging, reset or cleanup was used.

## Remaining problems and next executable steps

1. No candidate clears after-cost promotion. Further direction research requires a genuinely justified mechanism and properly timestamped features, not tuning the rejected fade. Conditional volatility is a risk/abstention hypothesis, not directional alpha.
2. Build synchronized, correctly licensed bid/ask or tick replay with explicit quote-side fills and interval timing. M1 stop-first assumptions cannot identify true intraminute order or support exact holding-period deductions. Integrate observed snapshots as separate sources, never silently splice.
3. Validate floating-equity drawdown, margin/minimum-lot feasibility and phase-specific constraints. Current closed-balance output explicitly says floating drawdown unverified. No breach or payout probability from this study is certified.
4. Obtain point-in-time release/consensus data and macro quote availability if testing announcement or cross-asset hypotheses. Existing daily proxies and event dates cannot establish that information set.
5. Resolve historical provenance failures transparently, preserving exploratory status. Do not create retroactive preregistrations. Full project-wide search count and PBO matrix remain incomplete.
6. Reconcile current Access rules against the intended plan/agreement/dashboard and broker contract; model news/short-trade deductions, margin, request approval and account-bound durable state. Production changes need separate owner authorization.
7. Review startup/state reset, process-specific updater/rollback, no-order isolation and operational watchdog issues in DEPLOYMENT_READINESS. Clean-install dependency verification and intended Windows demo-terminal measurements remain outstanding. No remote deployment access was used here.
8. Only after a frozen candidate passes engineering and evidence gates, authorize one untouched confirmation and prospective demo reconciliation. The22November deadline does not substitute for an adequate forward sample.

No background job is configured or promised. This checkpoint preserves completed work and explicit blockers for the next active session.

## Packaged checkpoint

Market/source/checkpoint commit: **0fcdbbd**. The local source review/demo-preparation ZIP was built and CRC plus per-file SHA256 verification passed for286 files. It is saved as `research/results/finalization_2026-11-18/finalization_demo_review.zip`; its generated `bundle_manifest.json` identifies the actual source revision and archive hash. Source is the explicitly hashed working tree, including preserved earlier pending code, not a claim of a clean immutable deployment release. No credentials, historical data, terminal binaries or installed dependencies are bundled. It does not enable no-order mode or start/deploy software. Prospective demo validation still requires the readiness steps and a dedicated verified account.

The engineering/research execution is saved. The mission's profitability and deployment qualification remain **not achieved**; the missing evidence is listed above. No research process is left running or scheduled to continue after this checkpoint.
