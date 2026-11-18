"""Heuristic P&L penalty scenario, NOT historical execution-delay replay.

No entry is shifted and no market observations are consulted. These assumed
penalties cannot establish latency sensitivity or be used as validation evidence.
"""
from typing import Dict, List, Any
import numpy as np


def evaluate_delay_sensitivity(
    trades: List[Dict[str, Any]],
    delays: List[int] = [0, 1, 5, 15],
    decay_rate_per_bar: float = 0.015,
) -> Dict[str, Any]:
    """Apply an assumed per-delay penalty to already-realized trade P&L.
    
    In latency-sensitive regimes (e.g. M15 / M5 breakouts), entering N bars late
    suffers adverse price excursion and spread decay.
    
    Args:
        trades: List of trade dicts or objects with 'net_pl'.
        delays: Bar delay offsets to test (e.g. [0, 1, 5, 15]).
        decay_rate_per_bar: Expected penalty / adverse drift factor per bar delay.
        
    Returns:
        Dict mapping delay to metrics (profit_factor, net_pl, pf_decay_pct).
    """
    if not trades:
        return {}
        
    pls = np.array([t.get("net_pl", 0.0) if isinstance(t, dict) else getattr(t, "net_pl", 0.0) for t in trades], dtype=float)
    
    results = {}
    base_pf = None
    
    for delay in delays:
        # Simulate adverse latency drift: each bar of delay imposes a slippage penalty
        # proportional to the average absolute trade excursion
        avg_abs = float(np.mean(np.abs(pls))) if len(pls) else 1.0
        penalty = delay * decay_rate_per_bar * avg_abs
        adjusted_pls = pls - penalty
        
        wins = float(np.sum(adjusted_pls[adjusted_pls > 0]))
        losses = float(np.sum(-adjusted_pls[adjusted_pls < 0]))
        pf = round(wins / losses, 4) if losses > 0 else (float("inf") if wins > 0 else 0.0)
        net = round(float(np.sum(adjusted_pls)), 2)
        
        if delay == 0:
            base_pf = pf
            decay_pct = 0.0
        else:
            decay_pct = round(((base_pf - pf) / base_pf) * 100.0, 2) if base_pf and base_pf > 0 else 0.0
            
        results[f"delay_{delay}_bars"] = {
            "method": "assumed_pnl_penalty_not_execution_replay",
            "empirically_calibrated": False,
            "delay_bars": delay,
            "profit_factor": pf,
            "net_pl": net,
            "pf_decay_pct": decay_pct,
        }
        
    return results
