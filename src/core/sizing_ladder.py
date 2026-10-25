"""
Position sizing ladder for small-account survivability.

Implements the ladder from REAL_MONEY_READINESS.md Part II.2.
"""

from typing import Tuple


class SizingLadder:
    """Account-balance-based position sizing with hard floors and caps.

    Single source of truth: risk_rules.SIZING_LADDER.  This class reads
    from it so there is exactly one ladder definition in the codebase.
    """

    POSITION_FLOOR = 50.0
    
    @classmethod
    def get_sizing(cls, balance: float) -> Tuple[float, int, float]:
        """(lots_per_order, max_concurrent_positions, max_total_exposure)."""
        if balance < cls.POSITION_FLOOR:
            raise ValueError(
                f"Balance ${balance:.2f} below position floor ${cls.POSITION_FLOOR:.2f}. "
                f"Trading halted."
            )
        from src.core.risk_rules import sizing_for_balance
        lots, max_vol, max_pos = sizing_for_balance(balance)
        return (lots, max_pos, max_vol)
    
    @classmethod
    def get_risk_pct(cls, balance: float, lots: float, stop_distance_usd: float) -> float:
        """
        Calculate actual risk percentage for given position.
        
        Args:
            balance: Account balance
            lots: Position size in lots
            stop_distance_usd: Stop loss distance in USD (not pips)
            
        Returns:
            Risk as percentage of balance (e.g., 0.05 for 5%)
        """
        risk_usd = lots * stop_distance_usd
        return risk_usd / balance if balance > 0 else 0.0
    
    @classmethod
    def is_safe_to_trade(cls, balance: float) -> bool:
        """Check if balance is above position floor."""
        return balance >= cls.POSITION_FLOOR
    
    @classmethod
    def format_sizing_table(cls) -> str:
        """Return formatted sizing ladder for display."""
        from src.core.risk_rules import SIZING_LADDER
        lines = ["Position Sizing Ladder (from risk_rules):", ""]
        lines.append("Balance Range | Lots/Order | Max Positions | Max Exposure | ~Risk/Trade")
        lines.append("-" * 75)
        for i, (upper, lots, max_exp, max_pos) in enumerate(SIZING_LADDER):
            if i == 0:
                lo = cls.POSITION_FLOOR
            else:
                lo = SIZING_LADDER[i - 1][0]
            hi_str = f"${upper:.0f}" if upper < float("inf") else "∞"
            balance_range = f"${lo:.0f}-{hi_str}"
            mid_balance = lo + 100 if upper < float("inf") else lo + 200
            est_risk_pct = cls.get_risk_pct(mid_balance, lots, 10.0) * 100
            lines.append(
                f"{balance_range:16} | {lots:10.2f} | {max_pos:13} | "
                f"{max_exp:12.2f} | ~{est_risk_pct:.1f}%"
            )
        lines.append("")
        lines.append(f"Position Floor: ${cls.POSITION_FLOOR:.2f} (trading halts below this)")
        return "\n".join(lines)


# Convenience function for main_loop integration
def should_halt_trading(balance: float) -> Tuple[bool, str]:
    """
    Check if trading should be halted due to low balance.
    
    Returns:
        (should_halt, reason)
    """
    if balance < SizingLadder.POSITION_FLOOR:
        return (
            True,
            f"Balance ${balance:.2f} below position floor ${SizingLadder.POSITION_FLOOR:.2f}"
        )
    return (False, "")


if __name__ == "__main__":
    # Display sizing ladder
    print(SizingLadder.format_sizing_table())
    print()
    
    # Test at various balances
    test_balances = [75, 105, 250, 500, 900, 1500]
    print("Examples:")
    print()
    
    for balance in test_balances:
        try:
            lots, max_conc, max_exp = SizingLadder.get_sizing(balance)
            risk_pct = SizingLadder.get_risk_pct(balance, lots, 10.0) * 100
            print(f"Balance ${balance:4.0f}: {lots:.2f} lots, {max_conc} positions, "
                  f"max {max_exp:.2f} exposure → ~{risk_pct:.1f}% risk/trade")
        except ValueError as e:
            print(f"Balance ${balance:4.0f}: HALTED - {e}")
