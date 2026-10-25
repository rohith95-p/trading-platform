# --- PORTFOLIO V6 (Donchian Trend — replaces losing V5 legs) ---
# Backtested 2026-10-25: profitable in all 3 OOS periods (PF 1.04/1.45/1.40).
# The V5 4-leg portfolio (TrendPullback, BBMeanReversion, NVMR, FVGNYTight)
# was net-negative (PF 0.73 DEV, 0.86 VALIDATE, 0.98 HOLDOUT).
#
# This portfolio runs a single daily strategy: 10-day Donchian breakout
# with EMA50 trend filter. It does NOT use the D1 EMA20 direction gate
# (it has its own EMA50 filter — the gate should be disabled for this magic).
#
# Pre-registration: research/registry/PREREG_MomentumPortfolio_2026-10-25.md

from src.strategies.momentum_strategies import DonchianTrendV6

PORTFOLIO = [DonchianTrendV6]
