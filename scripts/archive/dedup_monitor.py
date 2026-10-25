"""
Dedup Bug Monitor - catches stale candle deduplication early.
Run this alongside main loop to alert if dedup entries get old.
"""
import json
import time
from pathlib import Path

LOOP_STATE = Path("c:/projects/ultra_core/logs/loop_state.json")
MAX_AGE_MINUTES = 20  # Alert if any dedup entry older than this

def check_stale_dedup():
    if not LOOP_STATE.exists():
        print("✅ No loop_state.json (clean start)")
        return
    
    with open(LOOP_STATE) as f:
        state = json.load(f)
    
    if "last_fired_candle" not in state:
        print("✅ No dedup entries")
        return
    
    dedup = state["last_fired_candle"]
    current_time = int(time.time())
    max_age_seconds = MAX_AGE_MINUTES * 60
    
    stale = {}
    for strategy, candle_time in dedup.items():
        age_minutes = (current_time - candle_time) / 60
        if age_minutes > MAX_AGE_MINUTES:
            stale[strategy] = age_minutes
    
    if stale:
        print(f"🚨 STALE DEDUP DETECTED - RESTART BOT NOW")
        for strategy, age in stale.items():
            print(f"   {strategy}: {age:.0f} minutes old (limit: {MAX_AGE_MINUTES}m)")
        print(f"\nFIX: python scripts/restart_bot.py")
        return False
    else:
        print(f"✅ All dedup entries fresh (< {MAX_AGE_MINUTES}m)")
        return True

if __name__ == "__main__":
    check_stale_dedup()
