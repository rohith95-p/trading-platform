# Turtle System Two: fixed gold-only adaptations

Recorded before this runner's first output; previously inspected historical eras.
Primary source: Curtis Faith / OriginalTurtles.org rules, original publisher
https://tradingblox.com/originalturtles/originalturtlerules.htm and readable author-document
mirror https://www.tradingwithrayner.com/wp-content/uploads/2014/11/OriginalTurtleRules.pdf .
Prior project DONCH55 entries used13UTC/M15 risk+target geometry; this tests different exits.

XAUUSD only. M15 input, completed daily FX sessions at17NY (New York wall time+7h labels).
Prior55 completed-session high+.001 / low-.001 defines bid breakout entry. Always take
eligible System2 breakouts, no last-winner skip. N: SMA20 true-range seed then Wilder20,
all shifted one completed session. Initial stop2N from actual fill. Opposite20-session
channel exit is independently active; closest of hard stop and channel triggers liquidation.
No fixed profit target or scheduled daily liquidation. Both directions. One basket per arm.

Arm single: one .02lot unit. Arm pyramid4: add .02lot on favorable .5N moves from previous
actual fill, at most4 units; basket N frozen at first entry (explicit adaptation). Raise all
long stops / lower all short stops to last fill minus/plus2N. Units exit together. Report
basket win rate/PF and unit fill count separately: four units are not four independent bets.
No dynamic N-based account sizing or original multi-market diversification (user XAU-only).

Breakout chart is bid. Long fill max(open,trigger)+spread+slip; short min(open,trigger)-slip.
Short stop/channel trigger and exit use ask. Opening gaps receive adverse executable fills.
Each unit pays commission and funding from its own entry. Base ECN; stress spread2x/slip3x;
frictionless disables fees and funding, a counterfactual not broker performance.

M15 limitations: if both55 boundaries cross and opening quote doesn't identify direction,
skip and count ambiguity. Check existing stop before pyramid additions. New/addition-bar
stops pessimistically apply to full range; count ambiguity, require M1 replay for any survivor.
No exit/re-entry within the same M15 bar. Final open baskets explicitly liquidated on last
in-window close. Existing positions persist over data gaps, with opening-gap stops/funding.

Eras2005–11,2012–18,2019–25, fixed settings. Require base PF>=1.3, positive net and>=30
baskets per era before Atlas account tests. Report full metrics, cost sensitivity, ablation,
MC ordering, financing, basket/unit counts. No original futures-performance reproduction,
Atlas pass/protector/news/payout claim, or November2026 holdout access. Four units may
violate Atlas risk limits; this is signal research until sizing/MTM checks establish otherwise.
