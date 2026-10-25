"""DEPRECATED: Renamed to portfolio_v5_core.py.

This shim re-exports all portfolio classes and constants for backward compatibility.
Use `from src.strategies.portfolio_v5_core import PORTFOLIO` instead.
"""
from src.strategies.portfolio_v5_core import (
    PORTFOLIO,
    RETIRED_LEGS,
    PORTFOLIO_6_LEG,
    TrendPullbackV5,
    BBMeanReversionV5,
    NVMRPortfolioV5,
    FVGNYTightV5,
    PDHLRStrategyV5,
    NYLiquidityExpansionV5,
)

__all__ = [
    "PORTFOLIO",
    "RETIRED_LEGS",
    "PORTFOLIO_6_LEG",
    "TrendPullbackV5",
    "BBMeanReversionV5",
    "NVMRPortfolioV5",
    "FVGNYTightV5",
    "PDHLRStrategyV5",
    "NYLiquidityExpansionV5",
]
