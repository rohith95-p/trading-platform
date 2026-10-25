# Best strategies of 2026 + Atlas Funded entry guide (2026-10-16)

## Part A — Strategies, 2026 only (2026-01-01 → 2026-10-13)

Method
- **Full-engine run (42 strategy classes):** every class in `src/strategies/` including `archive/`, run solo through the corrected engine (entry bar tested; M1 fills from July, corrected coarse before), 0.01 lot, $10k start (no ruin truncation), `realistic_ecn` costs, live trading window (06:00–21:30 IST) and D1 gate. Runner: `scripts/research/all_strategies_2026.py`.
- **Candidate-library screen (320 rules):** tier-1 screener, 2026 vs 2025 (persistence) vs 2022-24. Not the same engine: no D1 gate, no portfolio interaction, half-spread only.
- 9 classes produced **0 trades** (EMA_STACK, KELTNER, PDHL_BREAKOUT, QQE, ASIAN_BREAKOUT, LUXALGO_FVG, TREND_SNIPER_SAR, MACD_CROSS, LKOCS_LONDON) — they are either outside the trading window or fail silently in the engine; they are untested here, not "bad".

### Honest framing
2026 is 9.5 months of one regime, and I am picking winners from ~360 tests: expect the best to be partly luck (winner's curse). Every breakout/continuation rule below was **PF 0.7–0.95 in 2022-24 and > 1.15 in 2025-26**: they are profiting from gold's strong trend / high volatility. A regime change will hurt them.

### Top 10 now

| # | Strategy | Source | 2026 PF | 2026 trades | Persistence | Caveat |
|---|---|---|---|---|---|---|
| 1 | H1 Donchian 100, SL3/TP9 | engine | **2.01** | 64 | 2025 PF 1.9; 2022-24 PF 0.81 | small n; trend beta; needs wide stops (prop-size account) |
| 2 | FVG_NY_SWEEP (liquidity-sweep FVG) | engine | 1.34 | 139 | Aug–Oct negative | loses money in last 4 of 10 months |
| 3 | SUPERTREND_EMA (archive) | engine | 1.31 | 122 | not tested earlier | Mar/Apr/Oct negative |
| 4 | SQUEEZE_ASIA | engine | 1.27 | 140 | — | −$256 in April; window clips its Asia session to 06:00-11:30 IST |
| 5 | BB_MEAN_REVERSION_V5 (live leg) | engine | 1.25 | 187 | 4-yr PF 0.86 | only leg that is positive in most 2026 months |
| 6 | LIQ_SWEEP_REVERSAL | engine | 1.25 | 157 | — | previously rejected (HYP-070) |
| 7 | XV2-104 time-of-day relative-move continuation [Asia] | screener | 1.33 | 476 | 2025 1.18; 2022-24 0.83 | most trades = most reliable stat (z≈6.9) |
| 8 | XV2-111 Change of character [Asia] | screener | 1.31 | 153 | 2025 1.28; 2022-24 0.69 | best 2025↔2026 consistency |
| 9 | XV2-108 BOS + retest [London] | screener | 1.42 | 71 | 2025 1.19; 2022-24 0.86 | small n |
| 10 | XV2-078 Round-$50 decisive break [Asia] | screener | 1.26 | 279 | 2025 1.18; 2022-24 0.95 | — |

Also positive in both 2025 and 2026: XV2-095 vol-spike continuation (1.23/1.35), XV2-084 noise-band break London (1.29/1.16), XV2-132 squeeze break Asia (1.23/1.15).

Other facts from the run
- **Losing in 2026 (full engine):** TREND_PULLBACK_V5 PF 0.84 (−$434), EURUSD_ASIAN_RANGE 0.80, MORNING_MOMENTUM 0.72 (−$1,104), EMA_PULLBACK 0.80, TRENDLINE_EMA8_SCALP 0.94 (1,240 trades), PDHLR 0.71, NY_LIQ_EXPANSION 0.52, SESSION_BREAKOUT 0.30.
- **FVG_NY_TIGHT_V5 (live): PF 1.07**, NVMR_V5 1.18 (95 trades), BB 1.25 — so in 2026 alone the live portfolio is mildly positive, but TREND_PULLBACK_V5 (55 % of the live trades) is negative.
- **Screener:** 110 of 274 candidates were profitable in 2026, only 50 also in 2025, 8 cleared PF > 1.15 in both.

What would be needed before trusting any of these: run the top ones through the full engine with the live gates, walk-forward by month, and forward-test on demo for ≥ 8 weeks.

---

## Part B — Atlas Funded: how to get in, what happens, what it costs

Everything below is from Atlas's own site/docs where I could read them; items marked **(conflict)** differ between Atlas pages or third-party sites. Re-check on the day you pay.

### What it is
- Trading name of **ATLAS VANQUISH FZCO**; registered entity **Atlas Funded LTD (Saint Lucia)**, offices St. Lucia, England, Dubai; terms governed by **UAE law**, arbitration.
- **Simulated trading only.** Atlas is not a broker; no trade reaches a live market. "Payouts are real rewards based on simulated performance." If Atlas stops paying, you have no market position to fall back on.

### The Access model (the cheap one)
- Pay **$5 to start**; "pay the rest of the fee only once you pass"; fail = owe nothing more. (A $1 version appears on one help page; the main site says $5.)
- No time limit, no minimum trading days; sizes $10K–$400K on the selector (marketing says funded up to $200K).
- Platforms: **MT5, TradeLocker, Match-Trader**. Forex/CFD and futures; **gold/XAUUSD is not named anywhere on the pages I read** — ask support for the exact symbol and leverage (their docs say leverage up to 1:100 on 1-Step Pro).
- Evaluation numbers **(conflict):** one official page: Step-1 target 3 %, max trailing loss 7 % (6 % funded), daily 5 % (3 % funded). Another: 10 % evaluation / 6 % funded drawdown. A third-party review: 5 % target, 3 % daily, 8 % max. Get the figures from your own dashboard before trading.
- Fee after passing **(third-party, unverified):** ≈ $78 for a $5K account up to ≈ $2,748 for $400K. Per-size fee is not on the pages I could read; the checkout page shows it.

### Steps (as far as the docs show)
1. Create an account at app.atlasfunded.com → "Get funded" (app.atlasfunded.com/purchase) → choose **Access**, size, platform (MT5).
2. Pay $5. Listed methods: Visa, Mastercard, Apple Pay, Google Pay, PayPal, Bitcoin "+12 more". **Use a card or PayPal** (dispute rights); avoid crypto.
3. Sign the contract and receive credentials (docs sections "contract signing → credentials → platform login → MT5 server"); I could not open those articles, so the server name and timing are unconfirmed.
4. Trade the evaluation. Rules are shown before you pay; breaching a hard limit ends the account.
5. If you pass: pay the remaining fee → funded account. **KYC (ID + address) is required before payouts.**
6. Request payout from the dashboard. Site: payout in 1–5 business days / "within 24 h or Atlas adds $1,000".

### Payout facts
- Split **80 % default (site says 90 % standard in the docs hub)** (conflict); 100 % as a paid add-on.
- First payout ≈ 28 days after funding (21 with weekly add-on), then every 14 days; first on-demand payout capped at 50 % split; min $100 ($3,000 for crypto); needs **5 qualifying days** (daily gain ≥ 0.5 %–1 %) before each payout.
- Fee refund with the **3rd** qualifying payout (Terms) — help articles say 4th/5th for some models (conflict). Add-ons never refunded.
- Grounds for withheld payout (Terms): rule breaches, "suspicious activity", failed/refused KYC, AML checks, "major unexplained strategy change" (§4.3).

### Rules that touch our bot (from Atlas's Trading Rules page)
- **EAs allowed without approval** (Rules page) — but the Terms say "some EAs allowed, you must ask first" (conflict) → get written approval from support.
- **Trades held under 3 min (one section says 2): profit deducted at payout**; "strategies built on trades under three minutes" are prohibited. → our four live legs, which close in minutes, are exposed.
- HFT, tick scalping, latency arbitrage, reverse trading, martingale/gambling-style: prohibited.
- **No opening new positions on Saturday/Sunday** (holding is OK).
- News: unrestricted in evaluations; on funded accounts profits from trades opened/closed within **5 min** of high-impact news are deducted.
- **Consistency:** a single day may not exceed **25 %** of cycle profit (1-Step funded) / 20 % (Instant Funded) — blocks the payout, doesn't breach the account. (Terms page says there is no rule by that name — conflict.)
- Funded accounts: risk on one instrument ≤ 50 % of the daily-loss limit; inactivity: ≥ 1 trade every 30 days.
- VPN allowed, but **disclose location changes in advance**; one account per person, no sharing, no cross-firm hedging or copying.
- Daily loss resets at midnight UTC and counts from the previous day's highest equity/balance.

### Trust summary
Positives: named entity, written rules, EA allowed on paper, $5 entry, no time limit, payout-delay guarantee.
Negatives: offshore entity, simulated accounts, rules differ between pages, Trustpilot complaints about denied payouts (reasons cited: "mostly long positions", multiple IPs), a malware-scan site rated it "moderate risk", and most review sites are affiliates.

### How to prove it is worth it (before and after paying)
1. **Don't pay for 2 weeks.** Run the chosen strategy in observe-only mode on your Exness demo; compare each signal with what the engine predicts (`weekly_divergence_check.py`).
2. **Decide the stop-loss on the experiment in advance:** total fees you will spend (e.g. $5 now, nothing more until criteria met).
3. **Criteria to buy a funded fee (the $78+):** ≥ 8 weeks of forward demo with PF > 1.2, max drawdown under 60 % of the firm's limit, ≥ 100 trades, no single day > 20 % of profit, and no trade under 3 min.
4. **Proof the firm pays:** payout needs KYC + 5 qualifying days + 28 days — so the first real proof is ~5–6 weeks after funding. Request the smallest payout first, and only scale (extra accounts/add-ons) after one lands.
5. **Break-even math:** at $5K, fee ≈ $78, split 80 %; to profit you need payouts > fee. With a target of ~3-5 % ($150–250) per cycle, one payout covers it — if you can pass at all. Probability of passing is the whole question, and none of my tests give a reliable edge yet.

### Email to send before paying
1. Exact XAUUSD symbol name, leverage, contract size on the MT5 server; the server name.
2. Access evaluation: profit target, daily loss and max drawdown (static or trailing), funded-phase numbers, and the fee per size.
3. Is my Python/MT5 external EA allowed without approval? Please confirm in writing.
4. Minimum hold time: 2 or 3 minutes; what is deducted and how.
5. Consistency rule: which models, what formula, challenge or funded only.
6. Is one-directional trading ever a breach? (Trustpilot: "mostly took long positions".)
7. VPS/IP: may I run from one fixed VPS, and what counts as a prohibited IP change?
8. Is the $1 Access offer available, and is Access refundable at the 3rd payout?
