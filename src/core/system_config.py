"""Single source of truth for 'what configuration is this run actually using.'

The project has repeatedly drifted: exposure caps raised in execution_handler.py
without the backtest that validated portfolio_v4 ever being re-run against the
new caps; a strategy-code fix (HYP-046) silently changed what an unrelated
holdout script tested; EngineConfig's own defaults still reproduce three
already-fixed live bugs. Every incident had the same shape -- a value lives in
more than one place, and nothing enforces they stay in sync.

SystemConfig captures every value that changes a backtest result (live-side
constants, per-strategy stop/target/session/dedup settings) into one object,
from either the live modules (`from_live()`) or a backtest run
(`from_engine_config()`), so the two are directly comparable. `fingerprint()`
hashes it; `diff()` says exactly which fields differ. See
validation_ledger.py for the record-and-check layer built on top of this.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    magic: int
    candidate_id: str
    session: Tuple[float, float]
    sl_atr_mult: float
    tp_atr_mult: float
    edge_trigger: bool
    execute_immediately: bool


@dataclass(frozen=True)
class SystemConfig:
    symbol: str
    fixed_lot_size: float
    max_concurrent_positions: int
    max_same_direction_positions: int
    max_total_volume: Optional[float]
    enable_trailing: bool
    enable_pyramiding: bool
    enable_d1_gate: bool
    direction_gate: str  # "d1_ema20" | "none" | any BacktestEngine variant name
    daily_loss_limit_pct: float
    # Owner rule 2026-09-06: 11:30-21:30 IST only, no night trades. This
    # changes which legs can fire at all, so it belongs in the fingerprint.
    trading_window_ist: Optional[Tuple[float, float]]
    risk_rules_enforced: bool
    # Macro override: strict short stops from DAILY_MARKET_ANALYSIS.md.
    # Two configs with different macro states have different fingerprints --
    # previously this was invisible to validation (2026-09-25 audit finding).
    macro_override_active: bool
    strategies: Tuple[StrategyConfig, ...]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @staticmethod
    def _strategy_configs_from_classes(strategy_objs) -> Tuple[StrategyConfig, ...]:
        cfgs = [
            StrategyConfig(
                name=s.name,
                magic=s.magic,
                candidate_id=getattr(s, "candidate_id", ""),
                session=tuple(getattr(s, "session", (0.0, 24.0))),
                sl_atr_mult=float(getattr(s, "sl_atr_mult", 0.0) or 0.0),
                tp_atr_mult=float(getattr(s, "tp_atr_mult", 0.0) or 0.0),
                edge_trigger=bool(getattr(s, "edge_trigger", False)),
                execute_immediately=bool(getattr(s, "execute_immediately", False)),
            )
            for s in strategy_objs
        ]
        return tuple(sorted(cfgs, key=lambda c: c.name))

    @classmethod
    def from_live(cls) -> "SystemConfig":
        """Snapshot of what main_loop.py would actually run right now."""
        from src.core import execution_handler as eh
        from src.core import main_loop as ml
        from src.core import risk_manager as rm
        from src.strategies.portfolio_atlas import PORTFOLIO

        from src.core import market_hours as mh
        from src.core import risk_rules as rr

        strategy_instances = [strat_cls() for strat_cls in PORTFOLIO]
        # Read the macro override state from a temporary RiskManager instance.
        # This ensures the fingerprint changes when the operator toggles the
        # RISK_OVERRIDE marker in DAILY_MARKET_ANALYSIS.md.
        try:
            from src.core.risk_manager import RiskManager as _RM
            _rm_tmp = _RM()
            _macro_active = _rm_tmp._strict_short_stops
        except Exception:
            _macro_active = False
        return cls(
            trading_window_ist=(tuple(mh.TRADING_WINDOW_IST)
                                if mh.ENFORCE_TRADING_WINDOW else None),
            risk_rules_enforced=rr.ENFORCE,
            macro_override_active=_macro_active,
            symbol=ml.SYMBOL,
            fixed_lot_size=eh.FIXED_LOT_SIZE,
            max_concurrent_positions=eh.MAX_CONCURRENT_POSITIONS,
            max_same_direction_positions=eh.MAX_SAME_DIRECTION_POSITIONS,
            max_total_volume=eh.MAX_TOTAL_VOLUME,
            enable_trailing=ml.ENABLE_TRAILING,
            enable_pyramiding=ml.ENABLE_PYRAMIDING,
            enable_d1_gate=ml.ENABLE_D1_GATE,
            direction_gate="d1_ema20" if ml.ENABLE_D1_GATE else "none",
            daily_loss_limit_pct=rm.DAILY_LOSS_LIMIT_PCT,
            strategies=cls._strategy_configs_from_classes(strategy_instances),
        )

    @classmethod
    def from_engine_config(cls, engine_cfg, strategy_instances: Sequence,
                           trading_window_ist=None,
                           risk_rules_enforced: bool = False) -> "SystemConfig":
        """Snapshot of what a BacktestEngine run actually tested, so it can be
        compared apples-to-apples against from_live()."""
        return cls(
            trading_window_ist=tuple(trading_window_ist) if trading_window_ist else None,
            risk_rules_enforced=risk_rules_enforced,
            macro_override_active=False,  # Backtests don't read DAILY_MARKET_ANALYSIS.md
            symbol=engine_cfg.symbol,
            fixed_lot_size=engine_cfg.fixed_lots,
            max_concurrent_positions=engine_cfg.max_concurrent,
            max_same_direction_positions=engine_cfg.max_same_direction,
            max_total_volume=engine_cfg.lot_cap,  # engine has no MAX_TOTAL_VOLUME analogue
            enable_trailing=engine_cfg.enable_trailing,
            enable_pyramiding=engine_cfg.enable_pyramiding,
            enable_d1_gate=engine_cfg.enable_d1_bias_gate,
            direction_gate=engine_cfg.direction_gate if engine_cfg.enable_d1_bias_gate else "none",
            daily_loss_limit_pct=engine_cfg.daily_loss_limit_pct,
            strategies=cls._strategy_configs_from_classes(strategy_instances),
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SystemConfig":
        d = dict(d)
        strategies = tuple(
            StrategyConfig(**{**s, "session": tuple(s["session"])}) for s in d.pop("strategies")
        )
        tw = d.pop("trading_window_ist", None)
        # Tolerate ledger entries written before these fields existed.
        d.setdefault("risk_rules_enforced", False)
        d.setdefault("macro_override_active", False)  # added 2026-09-27
        return cls(strategies=strategies,
                   trading_window_ist=tuple(tw) if tw else None, **d)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # ------------------------------------------------------------------
    # Fingerprint + diff
    # ------------------------------------------------------------------

    def fingerprint(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def diff(self, other: "SystemConfig") -> List[str]:
        """Human-readable list of exactly what differs from `other`."""
        out: List[str] = []
        a, b = self.to_dict(), other.to_dict()
        for key in a:
            if key == "strategies":
                continue
            if a[key] != b[key]:
                out.append(f"{key}: live={a[key]!r} vs validated={b[key]!r}")

        by_name_a = {s.name: s for s in self.strategies}
        by_name_b = {s.name: s for s in other.strategies}
        for name in sorted(set(by_name_a) | set(by_name_b)):
            sa, sb = by_name_a.get(name), by_name_b.get(name)
            if sa is None:
                out.append(f"strategy '{name}': present in validated config, missing live")
            elif sb is None:
                out.append(f"strategy '{name}': present live, missing in validated config")
            elif sa != sb:
                sa_d, sb_d = asdict(sa), asdict(sb)
                for k in sa_d:
                    if sa_d[k] != sb_d[k]:
                        out.append(f"strategy '{name}'.{k}: live={sa_d[k]!r} vs validated={sb_d[k]!r}")
        return out
