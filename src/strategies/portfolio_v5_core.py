# --- PORTFOLIO V5 CORE (4-Leg Validated Core) ---
# Cleaned, authoritative portfolio with losing strategies removed:
# - REMOVED: EURUSD_ASIAN_RANGE (PF 0.83, -$1,980)
# - REMOVED: LIQUIDITY_SWEEP_REVERSAL (PF 1.001, +$4 essentially random)
# - REMOVED: FOREX_SESSION_MOMENTUM (PF 1.043, +$161 marginal, contributes to overlap losses)
# - RETIRED to archive: PDHLR_STRATEGY_V5 (PF 0.795, -$617.35)
# - RETIRED to archive: NY_LIQUIDITY_EXPANSION_V5 (PF 0.953, -$39.08)
# Validated Performance: PF 1.141, Net +$4,495.43, Max DD $1,250.45 (22.44%), 8,347 trades.

from src.strategies._deprecated.grid_strategies import TrendPullbackStrat, BBMeanReversionStrat
from src.strategies._deprecated.bible_strategies import NVMRStrategy as _NVMRStrategy
from src.strategies._deprecated.portfolio_v4 import _LiquidityFilteredFVG


class TrendPullbackV5(TrendPullbackStrat):
    def __init__(self):
        super().__init__()
        self.name = 'TREND_PULLBACK_V5'
        self.magic = 5001
        self.sl_atr_mult = 0.5
        self.tp_atr_mult = 1.5


class BBMeanReversionV5(BBMeanReversionStrat):
    def __init__(self):
        super().__init__()
        self.name = 'BB_MEAN_REVERSION_V5'
        self.magic = 5002
        self.sl_atr_mult = 0.5
        self.tp_atr_mult = 1.5


class NVMRPortfolioV5(_NVMRStrategy):
    def __init__(self):
        super().__init__()
        self.name = 'NVMR_TARGET_10_V5'
        self.magic = 5003
        self.sl_atr_mult = 0.5
        self.tp_atr_mult = 1.5


class FVGNYTightV5(_LiquidityFilteredFVG):
    def __init__(self):
        super().__init__()
        self.name = 'FVG_NY_TIGHT_V5'
        self.magic = 5005
        self.session = (17.5, 21.5)
        self.sl_atr_mult = 0.5
        self.tp_atr_mult = 1.5


# Retired drag legs moved to src/strategies/archive/retired_v5_legs.py
from src.strategies.archive.retired_v5_legs import PDHLRStrategyV5, NYLiquidityExpansionV5

# --- PRUNED CORE PORTFOLIO (4-Leg Validated Core) ---
PORTFOLIO = [
    TrendPullbackV5, 
    BBMeanReversionV5, 
    NVMRPortfolioV5,
    FVGNYTightV5
]

RETIRED_LEGS = [
    PDHLRStrategyV5,
    NYLiquidityExpansionV5
]

# Legacy 6-leg reference preserved for comparative audits
PORTFOLIO_6_LEG = [
    TrendPullbackV5, 
    BBMeanReversionV5, 
    NVMRPortfolioV5,
    FVGNYTightV5,
    PDHLRStrategyV5,
    NYLiquidityExpansionV5
]
