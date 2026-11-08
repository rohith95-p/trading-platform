"""The trial ledger and the holdout ledger.

Why this exists
---------------
The deflated Sharpe ratio (Bailey & Lopez de Prado 2014) is only as honest as
`N`, the number of configurations tried to arrive at a result. On 2026-11-09 the
best answer this project could give was *"a few hundred, I think"* -- so the DSR
had to be computed against a guess, and the correlation-aware effective count
could not be computed at all because **no variant's return series had ever been
saved**.

That paper also argues (p.6) that a holdout cannot prevent overfitting, because it
treats a result as a single trial: *"If we apply the holdout method enough times
(say 20 times for a 95% confidence level), false positives are no longer
unlikely: They are expected."* This repo had by then spent 2016-2022 three times
with nothing recording the fact.

Two ledgers fix both:

* **Trial ledger** -- one file per distinct trial under ``research/trials/``,
  holding the configuration, the result and the per-trade return series. `N` and
  `k_eff` become queries instead of recollections.
* **Holdout ledger** -- one file per *decision* use of a window under
  ``research/holdout_spends/``. Re-spending a window raises, so reuse becomes a
  deliberate, recorded act rather than an invisible one.

Why a directory and not an append-only file
-------------------------------------------
Searches here run `ProcessPoolExecutor` with several workers, all finishing
backtests at once. Concurrent appends to one JSONL interleave and corrupt it on
Windows. One file per trial, named by the trial's own hash, is race-free and
idempotent for free: the same configuration re-run writes the same filename and
is not double-counted.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRIAL_DIR = os.path.join(ROOT, "research", "trials")
SPEND_DIR = os.path.join(ROOT, "research", "holdout_spends")

DISABLE_ENV = "ULTRA_NO_TRIAL_LEDGER"

# Purposes that consume a window's innocence. A diagnostic read does not.
#
# "test" belongs here and was missed on the first pass: the vol-timing study was
# labelled `test` and the backfill filed it as a diagnostic, so 2016-2022 read as
# spent once when it had been spent twice. Anything that decides whether a
# candidate lives must be on this list, whatever it is called.
DECISION_PURPOSES = ("select", "confirm", "judge", "validate", "decide",
                     "test", "screen", "shortlist", "holdout")


class WindowAlreadySpent(RuntimeError):
    """Raised when a window used for one decision is used for another."""


def enabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip().lower() not in ("1", "true", "yes", "on")


def _commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def _canon(obj: Any) -> Any:
    """Make a config JSON-stable so the same trial always hashes the same."""
    if isinstance(obj, dict):
        return {str(k): _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 10)
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    return str(obj)


def trial_id(strategies: Sequence[str], window: Sequence[Any],
             engine_config: Optional[Dict[str, Any]] = None,
             cost: Optional[str] = None) -> str:
    """Deterministic id for one configuration-on-one-window.

    Re-running an identical trial must NOT inflate N, so the id deliberately
    ignores wall-clock time and anything else that varies between runs.
    """
    payload = _canon({
        "strategies": sorted(str(s) for s in strategies),
        "window": [int(window[0]) if window and window[0] else None,
                   int(window[1]) if len(window) > 1 and window[1] else None],
        "config": engine_config or {},
        "cost": cost or "",
    })
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def record_trial(strategies: Sequence[str], window: Sequence[Any],
                 pls: Sequence[float], engine_config: Optional[Dict[str, Any]] = None,
                 cost: Optional[str] = None, purpose: Optional[str] = None,
                 note: Optional[str] = None,
                 extra: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Record one trial. Idempotent, race-free, and never raises.

    Returns the trial id, or None when the ledger is disabled or the write fails.
    A failure here must never break the backtest that called it.

    `purpose` and `note` default to ULTRA_TRIAL_PURPOSE / ULTRA_TRIAL_NOTE, so a
    research script can label a whole run of backtests by setting them once
    instead of threading labels through every call site.
    """
    if not enabled():
        return None
    if purpose is None:
        purpose = os.environ.get("ULTRA_TRIAL_PURPOSE", "unspecified")
    if note is None:
        note = os.environ.get("ULTRA_TRIAL_NOTE", "")
    try:
        tid = trial_id(strategies, window, engine_config, cost)
        os.makedirs(TRIAL_DIR, exist_ok=True)
        path = os.path.join(TRIAL_DIR, tid + ".json")
        if os.path.exists(path):
            return tid                      # same configuration, already counted

        a = [float(x) for x in pls]
        n = len(a)
        wins = [x for x in a if x > 0]
        losses = [x for x in a if x < 0]
        gl = -sum(losses)
        mean = (sum(a) / n) if n else 0.0
        var = (sum((x - mean) ** 2 for x in a) / n) if n else 0.0
        sd = var ** 0.5

        rec = {
            "trial_id": tid,
            "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "commit": _commit(),
            "purpose": purpose,
            "note": note,
            "strategies": sorted(str(s) for s in strategies),
            "window_start": int(window[0]) if window and window[0] else None,
            "window_end": int(window[1]) if len(window) > 1 and window[1] else None,
            "cost": cost or "",
            "trades": n,
            "net": round(sum(a), 4),
            "profit_factor": (round(sum(wins) / gl, 4) if gl > 0 else None),
            "win_rate": (round(100.0 * len(wins) / n, 3) if n else None),
            "sharpe_per_trade": (round(mean / sd, 6) if sd > 0 else None),
            "engine_config": _canon(engine_config or {}),
            # the series is the whole point: without it k_eff cannot be computed
            "series": [round(x, 2) for x in a],
        }
        if extra:
            rec["extra"] = _canon(extra)

        tmp = path + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, separators=(",", ":"))
        os.replace(tmp, path)               # atomic, so a reader never sees half
        return tid
    except Exception:
        return None


def _load_all() -> List[Dict[str, Any]]:
    out = []
    for p in sorted(glob.glob(os.path.join(TRIAL_DIR, "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


def trials(purpose: Optional[str] = None, strategy_contains: Optional[str] = None,
           min_trades: int = 0, window_start: Optional[int] = None,
           window_end: Optional[int] = None) -> List[Dict[str, Any]]:
    """Every recorded trial matching the filters."""
    out = []
    for r in _load_all():
        if purpose and r.get("purpose") != purpose:
            continue
        if strategy_contains and not any(
                strategy_contains in s for s in r.get("strategies", [])):
            continue
        if r.get("trades", 0) < min_trades:
            continue
        if window_start is not None and (r.get("window_start") or 0) < window_start:
            continue
        if window_end is not None and (r.get("window_end") or 0) > window_end:
            continue
        out.append(r)
    return out


def count_trials(**kw: Any) -> int:
    """N for the deflated Sharpe. A number, not a recollection."""
    return len(trials(**kw))


def series_for(records: Iterable[Dict[str, Any]]) -> List[List[float]]:
    """Per-trade return series, for the effective-trial-count correction."""
    return [r["series"] for r in records if r.get("series")]


def effective_trials(records: Optional[Sequence[Dict[str, Any]]] = None,
                     **kw: Any) -> Dict[str, Any]:
    """k_eff over the recorded trials, so the DSR can use an honest N.

    K_eff cannot exceed the number of series supplied, so this refuses rather
    than return a flatteringly small N -- the trap found in `7eab239`.
    """
    recs = list(records) if records is not None else trials(**kw)
    ser = series_for(recs)
    if len(ser) < 2:
        return {"k_raw": len(recs), "k_eff": None, "refused": True,
                "note": "need >= 2 recorded series; got %d" % len(ser)}
    if len(ser) < len(recs):
        return {"k_raw": len(recs), "k_eff": None, "refused": True,
                "note": ("only %d of %d trials have a saved series; K_eff <= %d "
                         "by construction, which would understate N and inflate "
                         "the DSR" % (len(ser), len(recs), len(ser)))}
    from src.backtesting.metrics import k_eff_correction
    return k_eff_correction(ser, len(recs))


# ---------------------------------------------------------------------------
# Holdout ledger
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-") or "window"


def window_history(name: str) -> List[Dict[str, Any]]:
    """Every recorded decision that has consumed this window."""
    out = []
    for p in sorted(glob.glob(os.path.join(SPEND_DIR, _slug(name) + "__*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


def spend_window(name: str, start: int, end: int, purpose: str,
                 allow_respend: bool = False, reason: str = "") -> Dict[str, Any]:
    """Record that a window was used for a decision. Raises if already spent.

    Diagnostic purposes (anything outside DECISION_PURPOSES) are recorded but
    never refused -- looking at data is not the same as deciding on it.

    Re-spending requires `allow_respend=True` and a `reason`, both of which are
    written into the ledger. That is the point: reuse becomes a deliberate act
    with a name on it.
    """
    is_decision = str(purpose).lower() in DECISION_PURPOSES
    prior = [h for h in window_history(name)
             if str(h.get("purpose", "")).lower() in DECISION_PURPOSES]

    if is_decision and prior and not allow_respend:
        raise WindowAlreadySpent(
            "window %r has already been spent on %d decision(s): %s.\n"
            "Bailey & Lopez de Prado (2014) p.6: applying holdout repeatedly "
            "makes false positives expected.\n"
            "Use a window nobody has decided on, or pass allow_respend=True "
            "with a reason, which will be recorded."
            % (name, len(prior),
               ", ".join("%s@%s" % (h.get("purpose"), h.get("recorded_utc", "")[:10])
                         for h in prior)))

    rec = {
        "window": name,
        "slug": _slug(name),
        "start": int(start),
        "end": int(end),
        "purpose": purpose,
        "is_decision": is_decision,
        "respend": bool(allow_respend and prior),
        "reason": reason,
        "prior_decisions": len(prior),
        "recorded_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": _commit(),
    }
    if enabled():
        try:
            os.makedirs(SPEND_DIR, exist_ok=True)
            # Microseconds AND a free-name search. A second-resolution stamp let
            # four spends in the same second overwrite each other, silently
            # destroying the audit trail this ledger exists to keep (found by
            # test_diagnostic_use_is_recorded_but_never_refused, 2026-11-09).
            stamp = re.sub(r"[^0-9]", "", rec["recorded_utc"])[:20]
            base = "%s__%s_%s" % (_slug(name), stamp, _slug(purpose))
            path = os.path.join(SPEND_DIR, base + ".json")
            n = 0
            while os.path.exists(path):
                n += 1
                path = os.path.join(SPEND_DIR, "%s-%d.json" % (base, n))
            tmp = path + ".%d.tmp" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass
    return rec


def spend_report() -> str:
    """Human-readable account of which windows have been consumed."""
    seen: Dict[str, List[Dict[str, Any]]] = {}
    for p in sorted(glob.glob(os.path.join(SPEND_DIR, "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                r = json.load(fh)
        except Exception:
            continue
        seen.setdefault(r.get("window", "?"), []).append(r)
    if not seen:
        return "no window has been recorded as spent yet"
    lines = ["%-26s %-9s %s" % ("window", "decisions", "uses")]
    for w in sorted(seen):
        rs = seen[w]
        dec = [r for r in rs if r.get("is_decision")]
        lines.append("%-26s %-9d %s" % (
            w, len(dec),
            ", ".join("%s@%s" % (r.get("purpose"), r.get("recorded_utc", "")[:10])
                      for r in rs)))
    return "\n".join(lines)
