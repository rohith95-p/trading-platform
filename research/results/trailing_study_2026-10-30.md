# Trailing the profit vs fixed target (2026-10-30)

Live 4-leg setup (daily gate on, protector off, 24h, 0.02 lots, Atlas guard, realistic ECN costs), M1 bars only.
Re-run: `python scripts/validation/trailing_study.py` (raw trades in the git-ignored JSON next to this file).

| Variant | DEV | TEST | RECENT | All: net | PF | Win rate | Max DD | Longest losing run |
|---|---|---|---|---|---|---|---|---|
| **Fixed stop + target (live)** | +$101 | +$856 | +$730 | **+$1,687** | **1.34** | 39% | $298 | 13 |
| Tight trail (0.7 / 0.3 ATR), target kept | −$113 | +$182 | −$128 | −$59 | 0.98 | 68% | $316 | 6 |
| No target, trail 1.5 ATR behind | +$103 | +$305 | +$212 | +$620 | 1.17 | 45% | $334 | 11 |
| No target, trail 2.5 ATR behind | +$204 | +$822 | −$114 | +$911 | 1.24 | 38% | $324 | 12 |
| Break-even stop at +2 ATR, target kept | +$67 | +$961 | +$460 | +$1,488 | 1.35 | 53% | $216 | 7 |

Verdict: trailing to the end earns less in every form; fixed targets stay. The break-even stop is the only
variant close to fixed (−12% profit) and it is smoother (max DD $216, longest losing run 7).
