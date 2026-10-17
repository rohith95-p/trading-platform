# Worst-case review of 7 shortlisted repos (2026-10-18)

Method: read-only. WebFetch/WebSearch only (GitHub pages, raw.githubusercontent.com, mql5.com). Nothing cloned, downloaded or executed.
CAVEAT: WebFetch returns small-model summaries, not raw bytes. Quoted parameter values are high-confidence, not byte-verified. Several summaries were self-inconsistent and are flagged. The STAR EA source is 2,635,305 characters; only about 10 chunks of 100k were read, so absence-of-evidence statements for it are weak.

Reference account: $5K Atlas Funded Access, 6% trailing equity DD ($300), 3% daily loss ($150), 3-min min hold, no weekend entries, news +/-5 min. XAUUSD at 0.01 lot is about $1 per $1 move.

---

## 1. codedpro/mt5-trade-split-manager
- Exists. Public, `main`. 86 stars, 21 forks, MIT, 5 commits, 1 open issue (#13, 2026-09-29, "make compose refuse to start without an API_KEY"). Commit dates not shown.
- Files: `bulk-add-signals.mq5` (v4.20), `server.py` (FastAPI), `mcp_server.py`, `config.json`, Dockerfile, docker-compose.yml, tests, CI workflow. Not a "strategy" at all: an order-splitting executor.
- Author: Rodd Azad, "Founder of CodeNest", "Open to work", Seattle, 60 repos, 15 followers, 75 total stars. Other repos: Gamee-Cheats (game score cheat tool), boot-breaker-bot, landing-page templates. This repo is his portfolio piece and 86 stars is most of his visibility. No trading track record.
- What it does: HTTP (127.0.0.1:8080) -> Python -> raw TCP (127.0.0.1:5555) -> EA polls every 500 ms (`SocketCheckIntervalMs = 500`), places 1-10 pending/market legs. Default split 60/10/10/10/10. After TP2 closes, SL of remaining legs moves to TP1.
- Enforcement facts:
  - Pending orders only (BUY_STOP etc., GTC, expiration 0 = never expire). Weekend-pending orders can fill on Monday gap.
  - SL optional: `if(cmd.sl > 0)`, else 0. No minimum SL, no per-trade risk cap. Lot size is caller-supplied and server accepts any (default `lot_size` 0.1, no bounds in server.py).
  - Risk limits are weak: `MaxPositions 50` (checked per signal, not per leg, so a 10-leg group can overshoot), `MaxDailyLossPercent 5.0` (higher than Atlas 3%), `MaxSpreadPips 10`. Daily-loss baseline only refreshes inside validation, so the first order after rollover sets it; it only blocks new orders and never closes anything.
  - `HandleDeleteOrder` / `HandleClosePosition` do not check magic `20250117`: any manual or other-EA position can be closed.
  - Only the `OrderOpen` bool is checked; partial-leg failure still returns `"success":true`.
  - Auth: `API_KEY = os.environ.get('API_KEY','')` -> auth OFF by default. TCP side has no auth. `/health` and `/` unauthenticated. Any local process can place/close trades. Setting `HOST=0.0.0.0` exposes it.
  - Timeout (10 s, `REQUEST_TIMEOUT`) returns 504 but the EA may still execute: retry gives duplicate orders. `async` handlers block on `threading.Event.wait()`, stalling the event loop. Unbounded `command_queue`.
  - JSON parsed with `StringFind`; read loop stops at first `}`; error strings not escaped.
  - Mid-trade SL logic can be falsely triggered: "TP2 gone" is inferred from absence, so a manual cancel or SL hit on TP2 moves TP3+ SL to TP1.
- No WebRequest, no DLL, no `.ex5`. Cannot run in Strategy Tester (README says so), so no backtest possible.
- Performance claims: none (disclaimer: educational). README has placeholder `yourusername/mt5-bulk-order-manager` links and a pip-spacing inconsistency (30-pip examples vs 15-pip "standard").
- Atlas worst case: an LLM or script calling `/order` with no SL and a big lot, no API key, 10 pending legs left over the weekend; 3-min hold not enforced (SL-to-TP1 jumps can close legs fast); no news awareness; its 5% daily limit would let you blow the 3% rule. It adds attack surface (open local ports) to gain a feature (10-way split) that a prop account at 0.01 lot cannot even use: 0.01 lot cannot be split (min lot step 0.01 -> 60/10/10/10/10 is impossible; on 0.10 lot only).
- Verdict: STUDY ONLY (for the split/trailing idea and the per-request Envelope pattern). Do not run as is. The "AI-agent friendly" angle is an unauthenticated order-entry API.

## 2. Alfacentauree/qlib-mql5-ai-bot
- Exists. 2 stars, 0 forks, 2 commits. License not shown (no license file seen). Files: `AI_Qlib_Bot.mq5` (v5.00), `ai_server.py`, `train_qlib_model.py`, backtest scripts, `backtest_results_summary.csv`, `models/`, `qlib_lgbm_model.txt`, `run`, two guides.
- Author: Adil Ansari, India, 36 repos, 3 followers, "My Own company". Peers: MT5_PositionSizer etc. Beginner-level portfolio.
- Misleading description: the training script does NOT use Qlib. It reads local MT5 TSV exports from `history_data/` (not in repo). Only LightGBM. "Qlib" is branding.
- Training (`train_qlib_model.py`): label `next_return = Close.pct_change().shift(-1)`, `threshold = 0.0002`, 3-class (SELL/WAIT/BUY); `lgb.train(params, train_data, num_boost_round=150)`, `num_class 3`; NO validation, NO test split, NO early stopping. Features: raw `Open, High, Low, Close, Volume`, `trend_filter`, `bullish_sweep`, `bearish_sweep`, `hour_of_day`. Raw price levels are non-stationary, so the model memorises price regimes. A fixed 0.0002 threshold is applied to forex and gold alike (gold's bar return distribution differs; threshold of 2 bp vs spread on XAUUSD makes label mostly noise).
- Results CSV is therefore purely in-sample: XAUUSD Normal 1:2: 72 trades, 48.61% win, 33.0% return; PRO 1:3: 68.06% win (a 1:3 reward giving 68% win is a classic in-sample / look-ahead fingerprint); Trailing 68.06%, 26.05%. EURUSD PRO 95.24% win on 21 trades. Sample sizes 9-99 trades. No dates, costs, drawdown, OOS. The guide gives "5-star" ratings to rows by itself.
- EA (`AI_Qlib_Bot.mq5`): POSTs bar-1 OHLCV + bar-2 high/low + EMA200 to `http://127.0.0.1:8000/predict` (WebRequest timeout 1000 ms; requires URL whitelisting). Closed-bar features (good), but `hour` is taken from `TimeCurrent()` rather than bar time. No auth on the server. `InpMagicNumber = 554433`, `InpRiskPercent = 1.0` of `ACCOUNT_BALANCE` (balance, not equity), `InpMinConfidence = 0.55`, `InpFixedLot = 0.1`, `InpTrailMult = 1.5`.
  - No TP (`TP = 0`), SL = `l - |c-l|*0.1` (10% beyond the signal candle wick: arbitrary, can be a very wide stop on gold).
  - Missing: spread check, daily loss/DD limit, margin check, news/session filter, stop-level validation, `trade.Buy/Sell` return codes unchecked, HTTP status ignored.
  - Bugs per the review: after break-even `initial_risk = 0` -> trailing never runs; with `InpMoveToBE=false` partial close repeats every tick; `CopyBuffer` failure makes `ema200=0` so EMA filter silently disables; lot floor `MathMax(min_lot, ...)` can exceed 1% risk; position check ignores magic.
  - Server: `BASE_DIR` hard-coded `/home/add/Desktop/Git/qlib_mql5_bot`; missing model files skipped silently; errors return HTTP 200 with no signal; training/serving feature parity unverified. (A summary of the SMC override read "BUY without bullish_sweep == 0 becomes WAIT" which looks garbled; treat as unverified.)
- Atlas worst case: if the Python server dies the EA does nothing on error (safe-ish) but open positions with no TP still trail by the buggy logic; model confidence is meaningless OOS, so it trades near-random 1%-risk entries with wide SLs and no daily-loss stop. 1% of $5K = $50/trade but the 0.01-lot min can force risk above 1%.
- Verdict: REJECT. Only possibly study the HTTP-bridge shape. Backtest table is in-sample marketing.

## 3. KamranAliOfficial/GuardianBot-EA
- Exists, but the repo contains only `README.md` and `GuardianBot_Documentation.pdf`. NO `.mq5` and NO `.ex5` in the visible tree (README tells you to copy `GuardianBot.mq5`, which is not there; "View all files" link says tree may be longer, but the tree fetch also showed two files). 0 stars/forks, 6 commits, no license. v1.00, "last updated October 2025" (README); GitHub update date Oct 26, 2025.
- Author: Kamran Ali, Sukkur, Pakistan, "Sukkur IBA University", 27 repos, 24 followers. Mostly IBKR/Telegram/Solana/NFT/"AuroraPremiumEA" / "forex-ea-mt5-robotic-trading" (39 stars, 10 forks, "collection of EAs and non-repainting indicators"). Product-listing style repos; email in README (kamranalideveloper@gmail.com). No independent reviews found (web search returned nothing relevant).
- Claimed behaviour (README only, no code): per-symbol floating-PnL drawdown every second; `DefaultLimitPercent = 5.0`; example `PerPairLimits "EURUSD:4,GBPUSD:3,XAUUSD:8"`; `TotalAccountRiskPercent` example 15.0 (undefined in docs); `PauseMinutesAfterClose` example 60; `DailyStops` unit unstated. On breach closes that symbol's trades and pauses it.
- Unknowns that matter and that docs do not give: equity vs balance, base of the percent, daily reset time/timezone, restart persistence, whether `TotalAccountRiskPercent` does anything. It is per-symbol, not account-level: with 1 symbol (gold) the "XAUUSD:8" example would allow 8% = beyond Atlas 6% trailing.
- Runs as an EA on one chart in the same terminal: if terminal/EA dies, no protection. No source to audit.
- Verdict: REJECT (nothing to audit; the shortlist's "risk overlay / kill switch" claim is unsupported by the repo content). Study only the README's config concept.

## 4. TickForgeFX/trading-tools-portfolio
- Exists. It is a catalogue repo, not code: `README.md`, `products/` (18 folders, each only a `PRODUCT_PAGE.md` as far as seen), `screenshots/`. 0 stars/forks, 50 commits, no license, 1 repo on the account, no bio. NO source code (all `.mq5` products sold via MQL5 Market). README: "no entry arrows, no strategies and no profit claims here" (the repo description says "EAs, indicators, and backtesting", which the README contradicts).
- Items relevant: paid "Daily Loss and Drawdown Risk Manager" (MQL5 product 197828, MT4 197830), free "Prop Firm Drawdown and Daily Loss Guard" (184431, monitor/alert only), "Prop Firm Auto Close and Drawdown Lockout" (185183 per search snippet; the page fetch returned unrelated products, so that is unverified).
- MQL5 product page 197828 (via summary): price USD 30, v1.0, published 24 Sep 2026 (4 weeks old), 15 activations, no reviews on the product itself. Page lists seller as "Amal Yuldashev", which differs from "TickForgeFX" handle (unexplained; could be a real name behind the handle, but note it). Behaviour: equity-based, credit excluded; daily baseline selectable (start balance / start equity / higher of / day's high equity); reset hour in SERVER time (no default stated); overall limit static from account size or trailing from peak equity; acts at 90% (warns 80%); closes all positions on all symbols, deletes pendings, retries refused closes, closes any new trade while locked; daily lock ends at reset, overall lock needs manual clear with 30-minute delay; lock survives restarts per login. Needs MetaTrader running with the tool attached; "Trades placed from a phone or another terminal can't be closed while MetaTrader is closed." This is the most credible description in the batch, but it is a closed-source marketplace binary: unverifiable, brand-new, small user base.
- Free Guard: per search snippet daily limit default 5%, measured from start-of-day BALANCE against current equity, overall static or trailing; never trades. 5% default is wrong for Atlas (3%).
- Atlas worst case: same-terminal enforcement (terminal crash / VPS disconnect / lag = no kill), 90% trigger on a closed-source tool, daily reset in server time may not match Atlas's reset, 3-min min-hold not considered (closing within 3 minutes of open could violate it), tick-rate/slippage on gold can overshoot a 3% limit, and closing everything including positions other systems intended to hold. Tools cannot know the prop firm's exact (balance vs equity-high-water) rule unless configured manually.
- Verdict: STUDY ONLY for the spec (the feature list is a good checklist for your own kill switch). The GitHub repo itself has nothing to run. The MQL5 product: "usable as component after audit" is not possible without source; test only on demo.

## 5. MickMaestro/Machine-Learning-for-Financial-Forecasting
- Exists. 0 stars/forks, 4 commits, MIT. Folders `MQH, MQL5, Results, config, data, docs, header_files, models, plots, src`, `main.py`. MSc dissertation (University of Essex 2025), author Ibukunoluwa Michael Adebanjo, 4 followers, 9 repos (stock-return prediction, CAPM, MQL5-Codebase-Scraper). Honest academic tone.
- Symbols: GER40, NAS100, SP500, US30 on H1. GOLD IS NOT MENTIONED. Data range not stated. 80/20 chronological split; TimeSeriesSplit for tuning; threshold chosen by F1 on a 0.10-0.90 grid.
- Evidence: the one concrete count is GER40 H1: 31 profitable signals of 1,808 (1.7% positives); the docs call accuracy "near-meaningless"; sample header accuracy 0.9945 is not a result. No PF, Sharpe, DD, costs, slippage or live/OOS. Spread is not in the training CSV.
- Self-disclosed defects: MQH approximation is a linear regression explaining only R2 0.2-0.5 of the model's probabilities; in-repo exporter `Data_Exporter2.0.mq5` writes a legacy 15-column format and the exporter that produced the training CSVs is not checked in (cannot regenerate data); some quantile features used full-dataset stats (excluded from deployment); headers generated before 2026-07 must be regenerated; 2026-07 changelog fixed "label leakage, shuffled splits, feature mapping". Claimed SHAP / RFE / degradation detection are intentions not verified in code.
- Atlas worst case: a deployed EA is a linear approximation of a model with R2 ~0.3, trained on indices, so on gold it is untested noise.
- Verdict: STUDY ONLY (best-documented honesty of the batch; useful as a cautionary template of the pipeline and of how small the positive class is). Not a gold system.

## 6. Bodasaieswar/claude-trading-bot
- Exists. 18 stars, 2 forks, MIT, 35 commits, 1 open issue (#1 "local monitoring dashboard", 2026-08-30). Folders `agents, alerts, autotrader, mt5-ea, scripts, skills, src, strategies, tests`, `rules.json`, `CLAUDE.md`, `SECURITY.md`.
- Author: Sai Eswar Boda, Arizona; profile is full-stack/healthcare IT; 46 repos; 5 followers. Trading bot is a hobby project; README itself says "personal trading bot running on a demo account", "Use at your own risk". Clone URL in README points to a different owner (`eswarcareless/claude-trading-bot`).
- Architecture: Claude Code is only the SCHEDULER / conversational front end. The scan logic (`autotrader/scanner_lite.cjs`) is fully deterministic confluence scoring of LuxAlgo values read from TradingView Desktop via CDP port 9222 (needs paid LuxAlgo Premium, macOS, `/opt/homebrew/bin/node`, `/Users/saieswarboda/...` hard-coded paths, MCP server with 78 tools). Entry gate: score >= 40 plus a zone/signal condition. SL/TP are static values from `config.zones`, not computed from price; lot is fixed `risk.lot_size`. So "bridge to Claude" is marketing: no LLM validates or generates trade parameters in the loop (but a Claude Code chat command like "Short GOLD 0.05 lots" is executed on request - prompt-injection exposure exists only if you let Claude read untrusted text).
- File bridge (`MQL5/Files/signal.json` in, `ack.json` out) and EA `TV.mq5` (raw `OrderSend`): 
  - `InpSecret = "test123"` default; `if(JsonGetString(raw,"secret",secret)) { if(secret != InpSecret) return; }` -> if the key is ABSENT the check is skipped (auth bypass). Secret is plaintext in the same file.
  - `InpDefaultLot 0.1`, `InpPollMs 100`, `InpSlippagePts 30`, `InpMagicNumber 123456` (set on orders but NOT used to filter positions).
  - File never consumed/deleted; `last_id` only in memory -> stale ENTRY re-executes on EA restart; missing id falls back to `StringLen(raw)`; non-atomic write + no share flags -> truncated/partial read races, silent failures.
  - Direction: `if(dir=="BUY") ... else SELL` so any typo = SELL.
  - SL/TP not required, no side check, no stops-level check, no lot-min/max/step or max-lot cap; partial close rounds to 2 decimals; `CloseAllPositions/ClosePartial/Modify` match by symbol only (will close manual trades); sleeps inside `OnTimer`.
  - Mixed units: `sl_price` with `tp_points` drops TP.
- Safety rules claimed ("max 3 trades/day, max $50 daily loss, 2:1 R:R, weekends off") are only in the Node scanner. `risk.max_daily_loss_usd` is checked against `state.daily_pnl` which is never updated -> the daily loss limit NEVER triggers. Stop-outs by broker SL are not detected (state `open_position` stays true), `--dry-run` can still send live CLOSE/MODIFY, ack timeout (8 s) can orphan a position then re-enter -> duplicate. `rules.json` is a copy for crypto/stocks (watchlist BTCUSD, ETHUSD, SOLUSD, AAPL, TSLA, NVDA; 1W/1D/4H) and says "2% of portfolio per trade", i.e. inconsistent with the gold bot.
- Performance claims: none. Good.
- Atlas worst case: a stale `signal.json` re-fires at EA restart at 0.1 lot with no SL (0.1 lot gold = $10/$1 move: a $30 move = $300 = entire 6% trailing allowance), EA and scanner both unaware of account drawdown, weekend entry only blocked in Node layer, news filter absent (checklist text only).
- Verdict: STUDY ONLY (bridge pattern, SECURITY.md, and as a catalogue of the failure modes above). REJECT the EA as it stands.

## 7. NadirAliOfficial/STAR-EA-v11.20
- Exists. 44 stars, 8 forks, 3 watchers, 60 commits, 2 open issues (#2, #3, both opened by the author on 2026-09-21, i.e. self-made feature requests). License file present (type not shown). Files: `STAR_v11.20.mq5` (about 2.6 MB of source in ONE file), `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `.github/`. No `.ex5`.
- Author: Nadir Ali Khan "TEAM NAK", Sukkur Pakistan, 150 repos, 796 followers, 71 stars total, bio "AI Automation Engineer | Trading bots", Fiverr link, company site, "client's" EA repos, Fiverr helper tools, demo videos. Freelance/lead-gen account with high output rate (30 repos updated within a 16-day window). Same town as Kamran Ali (#3); no evidence of connection, just noting. Web search found no independent reviews either way (results unrelated).
- Source header shows the EA is internally named "EA ANGEL v11.20" and carries dozens of "FIX#nnn" notes; the repo name/README say STAR. Strong sign of heavy AI/iterative patching, or a rebrand of a bigger product.
- README claims: "12 regimes" but table lists 8 rows (rows group several, so partly explained); defaults README vs code do not match: README `RiskPercent 1.5`, `MaxConsecutiveLoss 3`, `NewsFilterMinutes 30`, `ATRMinPips 8`, `BreakoutBars 2`, `UseNeuralScoring true`; code seen `EA_RiskPercent = 1.2`, `EA_MaxConsecLossHalt = 4`, `News_MinsBeforeHigh/After = 30/30`, `EA_MaxSpreadPips = 30`, `EA_MaxDailyTrades = 5`, `EA_MaxOpenTrades = 1`, `EA_MinRR = 1.2`. A `UseNeuralScoring` input was not found in chunks read.
- Risk settings that matter (code): `EA_MaxDailyDrawdownPercent = 4.5`, `EA_MaxWeeklyDrawdownPercent = 8.0`, `EA_MaxTotalDrawdownPercent = 9.9`, `EA_StopOnDrawdown = false`, `EA_EmailOnDrawdown = true`. All exceed Atlas (3% daily / 6% trailing). With `StopOnDrawdown=false`, the "total limit" only closes positions "if `EA_StopOnDrawdown` is set" (per excerpt) - so by default it neither stops nor closes. `EA_AggRiskCap_APlus = 5.0`, `EA_AggRiskCap_A = 4.0`, `EA_AggRiskCap_Default = 2.5`, `AutoOpt_MaxRiskOverride = 2.0` => per-trade risk can go to 5% on an A+ signal; changelog also mentions "win streak -> multiplier up to 5.0x" (a later note says streak multiplier removed in FIX#321). Kelly sizing present (`kelly = MathMin(kelly, 0.25)` i.e. up to 25%). `balance <= 0 -> 10000.0` fallback. Daily start balance capped at `BacktestInitialBalance`. `_refEquity = min(rawEquity, BacktestInitialBalance)`: a hidden dependency on a backtest input in live logic.
- News filter: no WebRequest/calendar; hard-coded UTC times `int usNewsTimes[] = {13*60+30, 14*60, 14*60+30, 15*60}` via `TimeGMT()` (fixed clock times, ignoring DST shift and non-US/real calendar - i.e. not a real news filter; Atlas +/-5 min on actual event times is not satisfied).
- Neural net: custom `NeuralNetwork` struct, "trains on limited H4 samples", comments "unreliable @185t", "NN too uncertain on H4 to gate reliably", `g_nnReadyForUse` after min 30 trades; i.e. an online-trained toy net on tens of trades.
- Look-ahead: FIX#503b moved `CopyHigh(0..)` to `CopyHigh(1..)` "to remove look-ahead bias" (admits earlier look-ahead). Peak tracking uses `iHigh(0)` intrabar. Contradictory notes (FVG default OFF in FIX#194 vs true in FIX#203; partial split 50/25/25 vs 25/25/50).
- Per-pair/TF config table is hard-coded (e.g. `XAUUSD M5: c.sl_min[0] = 20.0; c.spread[0] = 50.0;`) -> curve-fitted parameters per symbol/timeframe. File persistence `ICT_Data/OptProfiles.csv` can override risk and SL/TP (hand-editable, "AutoOpt" self-modifying risk).
- Backtest claim: XAUUSD H1, "OHLC on M1" modelling (not real ticks), spread 60 (unit unstated; code uses 30 pips max), $1,000, 1:100, "last 12 months" with no dates: PF 2.57, win 62.5%, max DD 2.28%, net $225.40, avg win/loss 1.8R. No trade count, no data source, no OOS, no costs breakdown. 22.5% in 12 months with 2.28% DD and PF 2.57 from a 1.2-1.5% risk system on gold H1 is implausible-looking; trade count undisclosed. Compare your own finding that coarse M15/OHLC-model backtests inflate PF (M1 A/B PF 0.93 vs 1.38).
- Not verified (only about 10% of source read): order-send and result checks, hidden license locks, WebRequest. No `#import`, no `WebRequest`, no martingale/grid found in the chunks read.
- Atlas worst case: 4.5% daily DD limit and 5% per-trade risk allow a single bad A+ trade to breach the 3% daily rule; Friday close at hour 20 (broker time) leaves nothing for weekend if mis-set; hard-coded US news times; 2.6 MB file is not auditable in any reasonable time; 150-repo author is a freelancer: expect no maintenance guarantees.
- Verdict: REJECT (as a live component). STUDY ONLY for its changelog as a list of ICT-EA failure modes.

---

## Claims in the shortlist text that the repos do NOT support
(inferred from the task description of the shortlist; adjust to its exact wording)
1. "Qlib + LightGBM ML signals" (#2): the training script reads MT5 CSVs, does not use Qlib; no validation/test split at all; the performance table is in-sample.
2. "Risk overlay / kill switch" (#3 GuardianBot): the repo has no code, only README + PDF; per-symbol not account-level; no equity/balance/reset spec.
3. "Account-level circuit breaker / risk manager" (#4): the GitHub repo is a catalogue with no code; the closest real feature is a closed-source USD 30 MQL5 product (15 activations, no reviews). Its repo description ("EAs, indicators, and backtesting") contradicts the README ("no strategies").
4. "File-based bridge to Claude" (#6): the Claude link is a scheduler/chat front end; decisions are deterministic LuxAlgo scoring; mac-only, paid LuxAlgo; the claimed safety rules (daily loss) are not enforced (dead `daily_pnl`).
5. "AI bridge / order splitting" (#1): not AI; no strategy; unauthenticated by default; cannot split 0.01 lots.
6. "ICT concepts EA ... 12-scenario" (#7): README lists 8 regimes (12 only in grouped text), README defaults differ from code, news filter is fixed UTC times, and PF 2.57 backtest lacks any verification.
7. #5 is about indices (GER40, NAS100, SP500, US30) on H1; nothing about gold.
8. Any suggestion that these are "prop-firm ready": none enforce Atlas 3% daily / 6% trailing / 3-min hold / news +/-5 min / no-weekend; several defaults (5%, 4.5%, 8%, 9.9%) exceed it.

## Cross-cutting red flags
- No repo shows live/forward results; three show in-sample or unverifiable backtests (#2, #7, and #5 shows none).
- Unauthenticated local control channels (#1, #2) and a bypassable secret (#6).
- Position-management functions that ignore magic number (#1, #2, #6): they will touch manual and other-EA trades (relevant if you run your own V5 bot on the same terminal).
- Unchecked trade results and no SL requirement (#1, #2, #6).
- Network calls: #1 TCP localhost, #2 WebRequest localhost, #6 Telegram + CDP + file bridge; #7 none found. No DLL imports found in any (limited reading for #7).
- No scam/pump warnings found for any author. Web searches returned no independent reviews at all (neither positive nor negative); absence is not endorsement.

## Final table
| # | Repo | Exists / stars | Real code? | Key worst-case failure | Verdict |
|---|------|----------------|-----------|------------------------|---------|
| 1 | codedpro/mt5-trade-split-manager | yes / 86 | yes (MQL5+FastAPI) | no-auth order API, optional SL, any-lot, per-signal caps, 5% daily | Study only |
| 2 | Alfacentauree/qlib-mql5-ai-bot | yes / 2 | yes (but no Qlib) | in-sample ML, no OOS, no risk limits, buggy trailing | Reject |
| 3 | KamranAliOfficial/GuardianBot-EA | yes / 0 | NO (README+PDF) | nothing to audit; per-symbol 8% gold example | Reject |
| 4 | TickForgeFX/trading-tools-portfolio | yes / 0 | NO (catalogue) | closed-source paid binary, same-terminal, server-time reset | Study only (spec) |
| 5 | MickMaestro/ML-for-Financial-Forecasting | yes / 0 | yes (Python+MQH) | indices only, R2 0.2-0.5 approximation, 31/1808 positives | Study only |
| 6 | Bodasaieswar/claude-trading-bot | yes / 18 | yes (Node+MQL5) | secret bypass, stale re-fire, no SL, dead daily-loss check | Study only / reject EA |
| 7 | NadirAliOfficial/STAR-EA-v11.20 | yes / 44 | yes (2.6 MB MQL5) | 4.5%/5% risk caps, fake news filter, unverifiable PF 2.57 | Reject |

Rows to treat as unverified: #7 source largely unread (about 10% of 2.6 MB); #4 product-page details are from a marketplace page summary and one search snippet; #3 repo tree might contain more than the two files shown.
