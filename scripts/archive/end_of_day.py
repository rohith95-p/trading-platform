"""
End of Day Script
- Generates daily report automatically
- Saves to daily_trade_progress/ folder
- Can be called manually or scheduled
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])

from scripts.generate_daily_report import generate_daily_report

IST = timezone(timedelta(hours=5, minutes=30))

def main():
    print("\n" + "="*70)
    print("END OF DAY - Generating Daily Report")
    print("="*70)
    
    # Generate report for today
    today = datetime.now(IST).strftime("%Y-%m-%d")
    
    try:
        output_path = generate_daily_report(today)
        
        if output_path:
            print(f"\n✅ Daily report generated successfully!")
            print(f"📁 Saved to: {output_path}")
            print(f"\n💡 View all reports: daily_trade_progress/")
        else:
            print(f"\n❌ Failed to generate report")
    
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
