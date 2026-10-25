# Prop-firm due-diligence checklist

Purpose: verify each firm from your screenshot (Maven Trading, Atlas Funded, PropScholar, FundedNext) **before paying anything**.
I have not verified any claim in that screenshot; treat every number in it (fees, 90 % split, "activation fee deducted from profits") as unconfirmed until you see it in the firm's own terms.

How to use: for each firm, fill the table in §9. Any **RED FLAG** answer = stop. Save screenshots/PDF of the terms on the day you pay (terms change, and you may need them in a dispute).

---

## 1. Who they are (do this first, 15 minutes)

- [ ] Legal entity name, country of registration, and address are stated in the Terms (not just a brand name).
- [ ] Company age. Many cheap prop firms are < 2 years old. **RED FLAG:** no named entity or a registration you cannot find.
- [ ] Independent payout evidence: search "<firm> payout proof / scam / refused payout" on Trustpilot, Reddit, Discord, and look for *dated, verifiable* payout posts, not only the firm's own marketing.
- [ ] Who is the broker/liquidity provider and is the platform a real MT5 server (broker server name visible)? Many "funded accounts" are **simulated** — you are paid from the firm's revenue, not from market profits. That is legal but changes the risk: payouts depend on the firm staying solvent.
- [ ] Is the account type stated clearly: evaluation (simulated), "funded" (simulated or live), or "activation fee then live"? Get this in writing.
- [ ] Refund/chargeback policy; payment method (card gives chargeback rights, crypto does not).

## 2. Automated trading (EA) rules — the make-or-break item for your bot

Your system is an MT5 Expert/Python bot. Check the Terms for:

- [ ] "Expert Advisors / automated trading / bots **allowed**" stated explicitly for **both** the evaluation and the funded phase.
- [ ] **Python / external API trading** (not just an EA inside MT5) allowed? Your bot uses the `MetaTrader5` Python package from outside the terminal.
- [ ] Any ban on: copy trading, "trade copiers", HFT, latency arbitrage, tick scalping, martingale/grid, "reverse trading", hedging across accounts. (Your H1 trend strategy is none of these, but your *current* legs are very short-lived trades — check minimum trade duration.)
- [ ] **Minimum holding time** (e.g. "trades < 60 s don't count / are violations").
- [ ] Is running on a **VPS** allowed, and are VPS IPs restricted? Is **one IP / one device** required? Are you allowed multiple logins to the same account (your watchdog + `protect_profit.py` open a second MT5 connection)?
- [ ] Do they require you to disclose or get approval for your EA before the funded phase? **RED FLAG:** "we may reclassify automated strategies at our discretion".

## 3. Drawdown rules (this decides survival)

Write the exact numbers and definitions:

- [ ] **Daily loss limit**: % and base (start-of-day *balance* or *equity*?), reset time and timezone, and whether it counts **floating** P/L.
- [ ] **Max loss limit**: % and type:
  - **Static** (fixed from initial balance) — best for you.
  - **Trailing on balance/equity** (peak ratchets up) — much harsher; recompute your risk if this applies.
  - **Trailing that locks at breakeven** — fine, but find the lock point.
- [ ] Is the limit measured on **equity (intraday, includes open trades)** or closed balance? Equity-based trailing is the one that kills good strategies on a spike.
- [ ] What happens on breach: account closed permanently, or can you reset (cost)?
- [ ] Do spreads/swap/commission count toward the limits? (They do on equity.)
- [ ] My simulation says H1 trend has a **26–36R worst drawdown**. At 0.5 % risk that is 13–18 %; at 0.25 % ≈ 6.5–9 %. Compare with their limit; if the limit is ≤ 10 % you need ≤ 0.25–0.3 % risk per trade.

## 4. Targets, time limits and phases

- [ ] Profit target per phase (and phase count: 1-step / 2-step / instant).
- [ ] **Time limit** per phase. Cheap challenges often have none; some have 30 days. My simulation: at 0.5 % risk the median time to +8 % was ~150 days — impossible under a 30-day limit.
- [ ] **Minimum trading days** required (e.g. 5 / 10 days) and what counts as a "trading day" (min lot / min P/L).
- [ ] Can you pause/extend the challenge? Is there inactivity closure (e.g. 30 days with no trade — your H1 strategy trades ~2/week, so check).

## 5. News, session and weekend rules

- [ ] News restriction: window (e.g. 2 min before/after high-impact), which events, and whether it applies to **opening, closing, or holding** across news. Penalty: trade voided / profit removed / account closed?
- [ ] **Weekend holding** allowed? Overnight holding allowed? (Your trend strategy holds hours–days. Your bot flattens Friday 22:30 IST — decide which wins.)
- [ ] Swap/overnight charges: same as a normal broker, or extra fees? Is Gold's swap (long ≈ −$0.52/night per 0.01 lot on your Exness account) in line?
- [ ] Market-hours and rollover rules; any "no trading in first/last minutes" rule.

## 6. Consistency, risk and behaviour rules

- [ ] **Consistency rule**: "no single day/trade may be more than X % of total profit" (common values 30–50 %). A trend strategy earns in lumps — a rule like this can void a passing result. Get the exact formula and whether it applies in the challenge, funded phase, or only at payout.
- [ ] Max lot size / max open positions / max exposure per instrument; leverage on **XAUUSD specifically** (often 1:30–1:100 even when "1:500" is advertised).
- [ ] **Stop-loss required** on every trade? (Your bot attaches SL — fine.) Maximum risk per trade rule?
- [ ] Prohibited: holding through news, gambling-style risk (e.g. > X % on one trade), "lot-size jumping", account stacking, "bonus abuse". Ask what their detection triggers are.
- [ ] Which symbols are tradable and is the gold symbol named `XAUUSD` or something else (your code uses `XAUUSDm`; every symbol/lot-step/contract-size difference needs a config change).

## 7. Payout terms (where cheap firms differ most)

- [ ] **Profit split** (advertised "90 %"): is it from day one, or only after scaling milestones?
- [ ] "Activation fee deducted from profits": exact amount, when charged, and whether it is refunded or lost if you fail the funded phase.
- [ ] **First payout**: waiting period (e.g. 14/30 days), minimum payout amount, minimum profit before withdrawal.
- [ ] Payout frequency and method (crypto USDT/LTC only? bank? fees? KYC required?). For India: confirm **KYC and INR off-ramp** and any tax implications (get tax advice; payouts from foreign firms are income).
- [ ] Payout **approval conditions**: manual "risk-team review", EA review, consistency check — any clause allowing refusal for "unfair trading" without evidence.
- [ ] Is payment from a simulated account? If yes, what happens to your profit if the firm closes?
- [ ] Withdrawal history: find at least 3 independent *recent* (last 3 months) payout confirmations.

## 8. Costs and traps

- [ ] Total cost to reach first payout: challenge fee + activation fee + resets + data/platform fees. A "$5" entry may be only the first step.
- [ ] Reset/retake price, subscription vs one-time, auto-renew (disable it).
- [ ] Does the cheap plan use a **micro account** (e.g. $50–$500 "simulated" balance)? Then the payout cap is tiny and 0.01-lot minimums recreate the sizing problem you already have. Compute: balance × target % × split vs fee.
- [ ] Hidden conditions in the small print: "max payout cap", "payout only after 3 profitable cycles", "profit target resets after payout".
- [ ] Cooling-off/refund: can you get your money back if you change your mind within N days?

## 9. Per-firm scorecard

Fill one column per firm. Anything unanswered = treat as RED.

| Item | Maven | Atlas | PropScholar | FundedNext |
|---|---|---|---|---|
| Legal entity & country | | | | |
| Years operating / verified payouts seen | | | | |
| Account type (sim / live) | | | | |
| EA + Python API allowed (eval & funded) | | | | |
| VPS / multi-connection allowed | | | | |
| Min trade duration | | | | |
| Daily loss limit & base | | | | |
| Max loss: static / trailing, equity / balance | | | | |
| Profit target(s) / phases | | | | |
| Time limit / min trading days / inactivity | | | | |
| News rule | | | | |
| Weekend / overnight holding | | | | |
| Consistency rule | | | | |
| XAUUSD leverage & max lots | | | | |
| Symbol name / contract spec | | | | |
| Profit split & real payout cap | | | | |
| Activation / hidden fees | | | | |
| Payout wait, method, KYC, INR route | | | | |
| Refund policy / payment method | | | | |
| Total cost to first payout | | | | |

## 10. Red flags (any one = walk away)

1. Terms do not name a legal entity, or the site hides its jurisdiction.
2. EA/bot permission only in marketing text, not in the Terms.
3. Trailing **equity** drawdown with a tight limit (≤ 5 %) and no lock.
4. A consistency or "unfair trading" clause that lets them void profits at discretion.
5. Payout only in crypto with no verifiable recent payouts, or payout needs "risk-team approval" with no criteria.
6. Advertised price far below the market ($5 vs the usual $30–$500) with the real cost appearing later as an "activation" fee.
7. Pressure tactics: countdown timers, "limited accounts", Telegram-only support.
8. Reviews that are all brand-new or all identical in wording.

## 11. Test before committing

1. Email support with the exact questions from §2, §3, §6 and §7 and keep the replies; a firm that answers vaguely will pay vaguely.
2. Pay the **smallest** plan with a card (chargeback possible), and treat the fee as already spent.
3. Run the bot on that account in **observe-only mode** for a week first (no orders), to check symbol names, spreads, server time zone, and that your Python connection works with their platform.
4. Do **not** pay for a larger or second account until you have received one real payout.

## 12. How this connects to your strategy

- Leverage is not edge. What protects a prop account is **risk per trade** (0.25 % or less on a 10 % static limit), not the headline 1:500.
- The only candidate that scales to a large account (H1 Donchian) earned its profit in 2025–26 only; do not pay for an account on the assumption that result repeats. See `docs/DEEP_AUDIT_2026-10-16.md` §6.3.
- Your four live legs are not suitable for a prop account: PF < 1 on the corrected engine.
- A challenge fee is a bet at the firm's odds. Cap total fees you are willing to lose, in advance, and write the number down.
