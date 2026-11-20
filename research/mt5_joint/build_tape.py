"""Build the observed Luna notification tape, releasing source deals after their printed second."""
from pathlib import Path
from scripts.research.luna_six_month_audit import read_report

base = Path(__file__).resolve().parent
report = base.parent / "results/luna_four_year_20261120/arch48_default.htm"
_, deals = read_report(report)
events = []
volume = 0
for deal in deals:
    lots = round(deal["volume"] * 100)
    change = lots if deal["action"] == "in" else -lots
    remaining = volume + change
    assert remaining >= 0
    if not volume and remaining:
        event = 1 if deal["side"] == "buy" else -1
    elif not remaining:
        event = 0
    else:
        event = 2 if deal["action"] == "in" else 3
    events.append((int(deal["ts"]) + 1, event))
    volume = remaining
assert volume == 0
with (base / "LunaNotifications.mqh").open("w") as output:
    output.write("// Derived from the archived original Luna account. Times in UTC, released after the source second.\n")
    output.write("const long luna_event[][2]={\n")
    output.write(",\n".join("{%s,%s}" % e for e in events))
    output.write("\n};\n")
