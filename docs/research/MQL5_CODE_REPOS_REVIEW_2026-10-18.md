# MQL5 code repos review (balanced), 2026-10-18

Method: read-only, WebFetch only (GitHub pages and raw.githubusercontent.com). Nothing cloned, downloaded or run. WebFetch returns model summaries, so quoted values are high-confidence but not byte-verified. File sizes, last-commit dates and language bars were NOT shown by GitHub in any capture. Commit counts are as displayed. Line counts are model estimates.

Target: XAUUSD prop trader (Atlas: 6% trailing equity DD, 3% daily loss, 3-min min hold, no weekend entries, news +/-5 min).

Headline: all 9 repos exist. None is a prop-ready EA. None has a daily-loss/trailing-DD guard that works, none has a news filter, none has a min-hold timer, none has a weekend filter. The best-built code is small and educational (Nico0100, RAo797bit). Nothing here beats the existing Python backtester, risk rules and Atlas rule engine. The only potential value is as an MQL5 porting reference.

## 1. Nico0100-algo/MQL5-samples
- Exists. Files: EATemplate.mq5 (~400 lines est.), LICENSE, README.md. 0 stars / 0 forks, MIT, 3 commits. Owner profile blank; "runs strategies on live capital" is self-described only.
- Strengths: lot formula is correct and instrument-agnostic: `lossPerLot = (stopDistancePrice / tickSize) * tickValue; lots = riskAmount / lossPerLot` (no points/pips assumption, so fine for 3-digit gold; tickValue is in account currency per MQL5 spec). Closed-bar signals only (`fast[2] <= slow[2] && fast[1] > slow[1]`, ATR `atr[1]`). Magic AND symbol filter. No DLL/WebRequest, no martingale/grid. Honest README: "has no edge, and that is deliberate"; admits stop-retry "did not fire during testing", no news/spread filter, no stop-level check, hedging-only tested. Honest about real-tick vs bar-data gap (">28,000% vs -9%"), which matches our own finding that coarse-bar backtests inflate.
- Weaknesses: stops NOT sent with the order (`trade.Buy(lots,_Symbol,0.0,0.0,0.0,...)`, then PositionModify) so there is a naked window. Review found a real bug: the "position not found" branch sets `_awaitingProtection=true` before `_pendingStop` is computed, so SL 0 / stale SL can be applied. Rounding: `MathFloor` then `NormalizeDouble(lots,2)` can round UP (0.126 -> 0.13 with 0.001 step) and hardcodes 2 digits. DONE_PARTIAL treated as failure; no requote handling; infinite retry; no stop-level read. Sizing uses balance not equity. No daily loss, no equity guard, no spread filter, no margin check.
- Shortlist claims: "risk-based lot sizing from stop distance/tick size/tick value" SUPPORTED. "bar-close evaluation" SUPPORTED. "magic scoping" SUPPORTED. "verified stops with retry" PARTLY (retry exists, but entry is naked, and the pending-stop bug can apply SL 0, and retry is unbounded).
- Verdict: BORROW COMPONENTS (lot formula and closed-bar idiom only; do not take the stop-protection flow).

## 2. RAo797bit/mt5-demo-ema-ea
- Exists. Dirs: mql5/ (one file, EMA_Cross_Demo_EA.mq5, ~215 lines est.), python/, reports/, tests/ (test_backtest.py), LICENSE (MIT), README. 0/0, 3 commits.
- Strengths: SL/TP always sent with the order (`g_trade.Buy(lots,_Symbol,0.0,sl,tp,...)`), SL distance floors at broker minimum (`MathMax(atr*InpSLATRMult,minDist)`, respects stops and freeze level), volume normalised to step/min/max, margin pre-check, spread filter at entry (`spread <= InpMaxSpreadPoints`), reads shifts 1 and 2 (shift 0 only for new-bar time), hedging/netting-safe position finder, input validation, no DLL/WebRequest/martingale. README is candid: synthetic random-walk data, no edge. Reported results show cost handling done right in spirit: gross PF 1.04 (357.78 net, 992 trades) -> net -770.00, PF 0.92; OOS last 30% PF 0.93.
- Weaknesses: lots are FIXED (`InpLots = 0.10`), not risk-based. No daily loss/equity guard. Retcode only logged on failure, no retry. Closes on opposite signal then may skip re-entry (flat). Header refers to `../python/backtest.py`; we saw only the folder, could not confirm contents. Test names not visible (only "8 unit tests ... signal timing, no lookahead, costs, spread filter, stop-first" per README).
- Shortlist claims: "unit tests for no look-ahead, cost handling, spread filter, stop-first" SUPPORTED as README text only (test file exists, contents not read). "negative net result after costs" SUPPORTED (-770.00, PF 0.92, but on synthetic data, not gold). "Python reference backtester" LIKELY (python/ dir exists, not read). Any implication it is a validated strategy is NOT supported.
- Verdict: STUDY ONLY / borrow components (SL-at-order, stop-level clamp, margin check, test-per-bias-class idea). Our Python project already has the equivalent.

## 3. abebr/awesome-mql5-expert-advisors
- Exists. Experts/ (8 EAs per README), Indicators/ (7), Include/ (RiskManager.mqh ~44 lines, TradeManager.mqh ~89 lines), LICENSE (MIT), compile.log, compile_batch.log, compile_test.log. 0/0, 4 commits.
- Strengths: RiskManager lot math is correct: `moneyPerPoint = (tickValue/tickSize)*point; totalLossAtSL = stopLossPoints*moneyPerPoint; lot = riskAmount/totalLossAtSL`; guards zero tick size/value; floors to lot step; clamps to min/max. TradeManager: filters by symbol and magic, reverse position loop, stop only moves in favourable direction, step throttle, buy/sell logic correct.
- Weaknesses: RiskManager fails OPEN (`if(stopLossPoints <= 0) return(0.01);`), min-lot clamp can exceed risk, hardcoded `NormalizeDouble(...,2)`, no include guard, balance-based, no cost term. NO daily-loss, equity or DD logic anywhere in these two files. TradeManager trailing is FIXED-distance (`proposedSL = currentPrice - (trailPoints * point)`), NOT ATR; no PositionModify retcode check, no normalisation, no stop/freeze-level check, no deviation or filling set. README: "institutional-grade", "battle-tested", "100%" broker compatibility with no tests or results; only evidence is self-reported compile logs ("0 errors, 0 warnings", build 4153). I did not read the 8 EAs.
- Shortlist claims: "RiskManager.mqh" SUPPORTED. "break-even" SUPPORTED. "ATR trailing" NOT SUPPORTED (fixed points trail). "8 EAs" SUPPORTED by README count (not individually audited).
- Verdict: BORROW COMPONENTS (break-even/step trail skeleton, after adding retcode checks); marketing language is unsupported.

## 4. samiabat/ICT-Trading-Strategy
- Exists. Root: .github/agents, docs/ (CODE_REVIEW.md, ICT_Strategy_EA.mq5, MT5_TESTING_GUIDE.md, README.md), EURUSD15.csv, XAUUSD5.csv, PIVOT_CANDLE_SCALPER.mq5, robust_mq5.mq5, ict_trader.py, equity_fixed.png, file "x". 3 stars / 0 forks, 29 commits, license not shown. Note ICT_Strategy_EA.mq5 is in docs/, not root; README tree does not match actual listing.
- Strengths: readable structure (sweep / trend / FVG / MSS / session / execution split); closed-bar signals; one-position gate; daily trade cap; checks OrderSend result and retcode; SL always attached (`request.sl = stopLoss`); no martingale/grid/DLL/WebRequest. Author is unusually honest: README calls the Python result "unrealistic for live trading" and cites 10-30% annual / 15-25% DD as realistic.
- Weaknesses (from source review, ~550-600 lines est.): (a) likely never trades: `sweep.barIndex = 1` is never updated so the MSS guard `currentBar >= sweep.barIndex` fails. (b) lot sizing wrong: `pipValue = tickValue/tickSize*_Point; lot = riskAmount/(slPips*pipValue/_Point)` omits the 10-point pip factor (and pip = `_Point*10` is hardcoded, wrong for gold); result clamps to min lot, so risk is uncontrolled. (c) the 5% daily loss limit NEVER fires: it uses `ACCOUNT_BALANCE`, `g_dailyPnL` is only ever reset to 0.0 and never accumulated, blocks only (does not close), resets on server-time day-of-month. (d) session filter uses `TimeCurrent()` server time though labelled UTC. (e) pending orders not tracked, GTC, FOK fill on pendings, so stacking pendings is possible (grid-like exposure). (f) TP R is `MathRandomUniform(InpTargetMinR, InpTargetMaxR)` - random, non-reproducible. (g) ATR read at shift 0; trailing/BE are stubs; relaxed mode ignores trend by default. Headline: 1,986 trades, 59.3% win, return 513,418.8%, DD 8.39%, R:R 2.93 - on EURUSD 15m Python backtest, not gold, not the EA, and the README itself disowns it. MAX_TRADES_PER_DAY=40.
- Shortlist claims: "ICT_Strategy_EA.mq5 with session" SUPPORTED but mis-timezoned. "risk sizing" NOT SUPPORTED as working (pip-factor bug). "5% daily loss limit" NOT SUPPORTED (dead code path). Any gold performance NOT SUPPORTED (numbers are EURUSD, though XAUUSD5.csv exists).
- Verdict: STUDY ONLY / skip as code. The idea list overlaps what we already rejected (HYP-070 liquidity sweep).

## 5. forexstrategystudio/mql5-expert-advisors
- Exists. EMA_Crossover/ (EMA Crossover.mq5, README.md, assets/images), LICENSE (MIT), README. 1 star / 0 forks, 3 commits.
- Strengths: compilable .mq5 source; once-per-bar; one position per symbol; README honest about hedging/netting and FOK/IOC fill caveats, state loss on restart.
- Weaknesses: code-generator output from a no-code vendor (marketing repo), voting-block wrapper around a plain EMA(9)/EMA(21) cross; only exposed input is LOTS; SL/TP hard-coded; no risk sizing, no daily guard. I did not read the .mq5 source (only README summary).
- Verdict: SKIP.

## 6. GeneralTradingSarl/expert-mt5
- Exists. mql5_experts_mt5/ with at least 287 subfolders (100 listed, 187 omitted per fetch), README, a `trading-experts` link, .ipynb_checkpoints/. 17 stars / 8 forks, 4 commits, license not shown. Folder names include "Basic Martingale EA v3", "Advisor Based on RSI and Martingale", "Angry Bird (Scalping)", "Arbitrage Triangle", "At random", "Beginner Programming_ Moving Average Crossover with and without Martingale".
- Strengths: large mirror of public MQL5 CodeBase EAs (mostly 2010s) - useful as an idea catalogue.
- Weaknesses: unvetted third-party code, mass-scraped; README says "Every EA ... has been optimized" with no evidence; advertises paid custom-EA services (commercial lead-gen). Martingale/grid EAs present. Did not open any folder; .ex5-only content not checked.
- Verdict: SKIP.

## 7. zhutoutoutousan/profitable-expert-advisor
- Exists. 48 stars / 15 forks, 71 commits (master), LICENSE type not shown, .env.example, SECURITY.md. Dirs: ai, back-pedal, backtesting, docs, frontline, lab, paper, polymarket, scripts, self-coding-agent, strategy-tester (app.py, factor_tester/), plus frontline/ (cluster-latest, tradingview, united_template, units*, units_economic_calendar).
- Strengths: most active repo; has a Python factor tester, an economic-calendar unit, and a gold-specific EA name (EMASlopeDistanceCocktailXAUUSD) - the only repo that targets XAUUSD. Includes SECURITY.md and .env.example (credentials kept out of source by design).
- Weaknesses: README metrics for EMASlope XAUUSD: yearly return 28%, PF 1.222, recovery factor 7.17, expected payoff 1.3, Sharpe 4.11, max DD 14.00%, win rate 64.65%, 2863 trades. No data source, no cost/spread/commission, no OOS stated. 14.00% DD alone breaches Atlas 6%; Sharpe 4.11 with PF 1.22 and 64.65% win rate is internally odd (suggests inflated/coarse backtest or martingale-like payoff). The EA source was not found in visible listings (README points to an MQL5/ path); I could not confirm .mq5 vs .ex5. "polymarket", "self-coding-agent", "ai" dirs are scope creep and unaudited (possible network/telemetry; not checked). Project's own prior finding: coarse-M15 backtests inflate (M1 A/B PF 0.93 vs 1.38).
- Verdict: STUDY ONLY (metrics unverified; do not trust).

## 8. nawfdev/mq5_skills
- Exists. docs/, mql5-ea-expert/ (SKILL.md + references/), tools/, CHANGELOG, CONTRIBUTING, LICENSE (MIT), evals.json. 7 stars / 3 forks, 4 commits. Install command typo (`mq5_sklis`). README "Last updated: May 20, 2026".
- Strengths: it is LLM skill/prompt text, not an EA; its stated safety defaults are sane on paper (risk <=1%/trade, daily loss <=5%, max DD <=20%). Has evals.json.
- Weaknesses: NOT "actual .mq5 source you can compile" - no .mq5 visible. Its limits (5% daily, 20% DD) are far looser than Atlas (3% / 6%). Allows martingale (multiplier <=1.5, <=4 steps), which is prohibited in our context.
- Shortlist claim "actual .mq5 source": NOT SUPPORTED for this repo.
- Verdict: SKIP (prompt scaffolding; we do not need it).

## 9. gammarinaldi/mql5 (flagged grid/martingale)
- Exists. Dirs: Grid_BB_RSI_News_EA, Grid_EMA_Stoch, ORB_Strategy, Triple_Stochastic, gridmart_scalper (gridmart_scalper_mt5_ea_conservative.mq5), README. 0 stars / 2 forks, 12 commits, license not shown.
- Confirmed: README says "grid and martingale systems"; "Grid/Martingale lot management", "lot multipliers for grid levels", "Grid Mart Scalper ... grid and martingale principles". Claims news filter and equity-based drawdown limits, but I did not read source, so hard-SL presence and multiplier defaults are UNKNOWN. The ORB_Strategy folder is the only non-grid item (not read).
- Strengths: has a news-filter concept and equity-based DD limit feature on paper; ORB is a plain concept.
- Weaknesses: averaging/martingale is incompatible with a 6% trailing-DD prop account; "conservative" in a filename is not evidence.
- Verdict: SKIP (ORB folder could be skimmed, low value).

## Does any of this add value to our Python project?
Honestly: very little. We already have a backtester, risk rules and an Atlas rule engine. Possible small takeaways only if the owner ever wants an MQL5 EA port: (1) tick-value/tick-size lot formula (Nico0100 / abebr; ours should be checked for equivalence on the gold feed anyway), (2) SL-in-order plus stops-level clamp (RAo797bit), (3) closed-bar `[1]/[2]` signal reading, (4) break-even step skeleton (abebr). Everything Atlas-specific (equity-based trailing DD, daily loss close-out in broker-day timezone, 3-min min hold, weekend flat, news +/-5 min, partial-fill/requote handling) is absent from all repos and would have to be written. If an EA is wanted, the right starting point is our own Python logic ported, not any of these.

## Claims the repos do NOT support (inferred from quoted shortlist text)
- "ATR trailing" in abebr: not present (fixed-point trail).
- "5% daily loss limit" in samiabat: present as a variable but never accumulates; balance-based; blocks only.
- "risk sizing" in samiabat: pip-factor bug, clamps to min lot.
- "verified stops with retry" in Nico0100: entry is naked, pending-stop bug, unbounded retry.
- "actual .mq5 source" for nawfdev/mq5_skills: it is prompt text.
- Any performance claim usable for gold: samiabat numbers are EURUSD and disowned by the author; zhutoutoutousan XAUUSD numbers have no source/costs/OOS; RAo797bit numbers are synthetic and negative.
- "unit tests ... negative net result after costs" in RAo797bit: supported but only as README on synthetic data; it says nothing about gold.

## Closing table (10 lines)

| # | Repo | Strengths | Weaknesses | Fair verdict |
|---|------|-----------|------------|--------------|
| 1 | Nico0100-algo/MQL5-samples | Correct tick-value lot formula, closed-bar, honest README | Naked entry, SL-0 bug, no daily/equity guard | Borrow components |
| 2 | RAo797bit/mt5-demo-ema-ea | SL at order, stops-level clamp, margin/spread check, tests, honest | Fixed lots, no daily guard, synthetic data | Study only (borrow ideas) |
| 3 | abebr/awesome-mql5-EAs | Correct lot math, safe BE/trail loop, magic filter | No ATR trail, fail-open 0.01, no retcode checks, hype | Borrow components |
| 4 | samiabat/ICT-Trading-Strategy | Clean structure, honest README | Likely never trades, lot bug, dead daily limit, random TP | Study only |
| 5 | forexstrategystudio/mql5-EAs | Compiles, once-per-bar | Vendor template, one EMA cross, LOTS only | Skip |
| 6 | GeneralTradingSarl/expert-mt5 | 287+ EAs as idea catalogue | Unvetted scrape, martingale EAs, service ads | Skip |
| 7 | zhutoutoutousan/profitable-EA | Active, XAUUSD-specific, calendar unit | 14% DD, no cost/OOS, source not confirmed | Study only |
| 8 | nawfdev/mq5_skills | Sane-looking safety defaults | Not .mq5; limits looser than Atlas; allows martingale | Skip |
| 9 | gammarinaldi/mql5 | News filter / equity DD on paper | Grid and martingale by design, source unread | Skip |
| - | Overall | A few correct snippets | No repo meets Atlas rules; Python stack already ahead | Use none as foundation |
