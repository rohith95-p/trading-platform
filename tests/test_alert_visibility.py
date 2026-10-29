"""Halts and meaningful blocked signals reach Telegram, rate-limited; routine blocks stay silent (2026-10-21)."""
from src.core import alerts, ops, trade_log


def test_halt_latch_sends_one_critical_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send", lambda m, severity=None, context=None: sent.append((severity, m)) or True)
    ops.set_halt("monthly loss 31%", "risk_rules")
    ops.set_halt("second cause ignored", "risk_rules")          # idempotent: no second alert
    assert len(sent) == 1 and sent[0][0] == alerts.CRITICAL and "monthly loss" in sent[0][1]


def test_meaningful_block_alerts_once_per_hour(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "record_only", lambda m, severity=None: sent.append(m))
    monkeypatch.setattr(trade_log, "_blocked_alert_last", {})
    for _ in range(5):
        trade_log.signal("FVG_NY_TIGHT_V5", "SELL", "blocked", "spread > 250")
    assert len(sent) == 1 and "spread > 250" in sent[0]
    trade_log.signal("FVG_NY_TIGHT_V5", "SELL", "blocked", "max concurrent positions reached")
    assert len(sent) == 2                                        # a different reason is a different alert


def test_routine_blocks_stay_silent(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send", lambda m, severity=None, context=None: sent.append(m) or True)
    monkeypatch.setattr(trade_log, "_blocked_alert_last", {})
    trade_log.signal("BB_MEAN_REVERSION_V5", "BUY", "blocked", "D1 bias gate (BEARISH)")
    trade_log.signal("X", "SELL", "blocked", "measurement-only mode (no orders)")
    trade_log.signal("X", "SELL", "deduped", "already acted on this candle")
    trade_log.signal("X", "SELL", "fired", "")
    assert sent == []
