# Post-CPI/NFP gold reaction: no promotion

Official primary calendars: https://www.bls.gov/bls/news-release/cpi.htm and
https://www.bls.gov/bls/news-release/empsit.htm . Resolved 168 dated archive URLs,
including two December2018 data releases; excluded two releases occurring in2026.
166 actual releases during2019–2025. Of those,163 have complete minute0–60 windows.
Missing windows: CPI2020-04-10, NFP2021-04-02 and NFP2023-04-07. These dates coincide
with Good Friday; the screen records missing quotes, not invented event returns.
08:30 ET assumed throughout, with DST converted using America/New_York and archived
2024 CPI/NFP embargo times independently spot-checked. Individual embargo times were
not checked for every release; actual-date labels are not original schedule vintages.

Fixed rule: first15-minute directional response, market entry at minute16, stop one
initial range away, exit minute60 open. Two arms follow/fade; fixed .02 lots. Base costs
include executable bid/ask, $.02 adverse slip each fill, $.07 roundtrip commission.

| Arm | Era | Trades | Win % | PF | Net USD |
|---|---|---:|---:|---:|---:|
| Follow | 2019–21 | 70 | 40.0 | .668 | -111.10 |
| Follow | 2022–23 | 47 | 38.3 | .491 | -165.65 |
| Follow | 2024–25 | 46 | 37.0 | .682 | -162.40 |
| Fade | 2019–21 | 70 | 48.6 | .861 | -41.40 |
| Fade | 2022–23 | 47 | 59.6 | 1.577 | 106.77 |
| Fade | 2024–25 | 46 | 56.5 | 1.127 | 46.12 |

Neither passes PF>=1.3 in every era. Fade2022–23 survives the explicit cost stress at
PF1.385, but its 95% month-block resampled total-net interval is [-$36.88,+$244.93],
and its Bonferroni-adjusted random-direction p=.355. This stronger period does not
establish repeatable edge. Category subgroups change across eras: do not select the
winning release category/year after observing this output.

Frictionless follow remains losing in every era (PF .788/.558/.726), so its failure is
not explained solely by execution costs. Frictionless fade yields1.012/1.791/1.205;
costs reduce an inconsistent advantage rather than destroy a universally strong signal.
Cost scenarios replay stops separately because changing executable entry changes stop
placement. Differences between gross/net scenarios are not pure fee attribution.

Output: post_bls_reaction.json (category statistics, risk ratios, Monte Carlo order
resampling, ablations, conditional bootstrap, random-direction tests, cost stress).
Actual bar windows preserved in content-addressed research/data/bls_windows/*.npy;
calendar URL lists and content hash retained. Dated base returns join recovered matrix,
now22 candidate/execution versions including earlier superseded sweep-fill diagnostics.
This is a subset, not a complete independent strategy or trial count.

This is an economically motivated new rule, not an exact published strategy replication.
No actual-vs-consensus economic-surprise data used. Sparse monthly release opportunities
cannot alone provide everyday trading. M1 spread fields miss intraminute quote spikes;
other news windows, Atlas equity floors and payout eligibility are not proven. Historical
eras were already inspected; November2026 holdout untouched. No live configuration changed.

Tests cover official-URL validation, winter/summer timestamp conversion, executable short
ask exit costs, and excluding minute60's later extremes after its opening-time exit.
