"""Render the verified native-vs-Python results and modeled Atlas cash by phase."""
import json
from pathlib import Path

import pandas as pd

ROOT=Path("research/results/retained_mt5")


def render():
    rows=[]
    for p in sorted(ROOT.glob('*_audit.json')):
        d=json.loads(p.read_text())
        n=d['native_after_terminal_charges']
        ec=d['standardized_ecn']
        py=d['python']
        f=d['fill_comparison']
        a=d['native']['atlas']
        e=d['standardized_ecn_path']['atlas']
        rows.append(dict(year=d['year'],roster=d['roster'],phase=d['phase'],start=d['native']['start'],
                     native_trades=n['trades'],native_wins=n['wins'],native_win_rate_pct=n['win_rate_pct'],
                     native_net=n['net'],native_pf=n['pf'],native_report_drawdown=d['mt5']['Equity Drawdown Relative'],
                     native_all_quotes_max_drawdown_pct=d['native']['unrestricted']['max_equity_drawdown_pct'],
                     native_with_python_costs_net=ec['net'],native_with_python_costs_pf=ec['pf'],
                     python_net=py['net'],python_pf=py['pf'],
                     matched_minutes=f['matched_entry_minute_direction_strategy'],
                     native_only=f['native_only'],python_only=f['python_only'],same_exit_minute=f['matches_exit_same_minute'],
                     native_status=a['status'],native_time=a['time'],native_balance_at_status=a['balance'],
                     ecn_status=e['status'],ecn_time=e['time'],native_conditional_cash=a['modeled_cash_received'],
                     conditional_ecn_cash=e['modeled_cash_received'],native_known_profit_deductions=a['deductions'],
                     native_payout_dates='; '.join(pay['time'] for pay in a['modeled_payouts']),
                     span=d['mt5']['Period'],ticks=d['mt5']['Ticks'],exact_milliseconds=d['exact_fill_ms'],fills=d['fill_count']))
    df=pd.DataFrame(rows)
    df.to_csv(ROOT/'native_comparison.csv',index=False)
    txt=['# Native MT5 cross-check of three XAUUSD strategies',
         '',
         'Each year starts with a fresh $5,000 Access evaluation. A verified evaluation pass starts a new $5,000 funded simulation on the next trading date, at MT5 leverage of 1:50. The January–October 2026 and full-calendar 2025 windows use the same Exness quote archive as the Python tests.',
         '',
         '| Year | Book | Phase | Trades | Native net | Native PF | Native with ECN assumptions | Python net | First account event | Conditional cash |',
         '|---|---|---|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        status=r['native_status'].replace('_',' ')+' '+(r['native_time'][:10] if r['native_time'] else 'at cutoff')
        txt.append(f"| {r['year']} | {r['roster']} | {r['phase']} | {r['native_trades']} | {r['native_net']:+,.2f} | {r['native_pf']:.2f} | {r['native_with_python_costs_net']:+,.2f} | {r['python_net']:+,.2f} | {status} | {r['native_conditional_cash']:,.2f} |")
    txt+=['','## Interpreting the figures','','Trading P&L includes the full tester interval. An Atlas attempt ends at its first breach. Evaluation profit does not enter the funded account. A funded row with conditional cash assumes verified KYC and immediate approval and settlement. Deduct $5 entry and $78 activation once per activated attempt to obtain modeled cash after fees. The $100 cash receipt corresponds to $111.11 gross debited for the usual 90% split. After the first Protector liquidation the split drops to 50%. A second trigger breaches the account.',
         '',
         'Native fills are grouped by position ID and reconcile to the official tester deal list and terminal net profit. Marks use ordered Exness bid for longs and ask for shorts, entry-side native fees and native reported swap across accrued UTC rollovers. The ECN sensitivity reprices each original MT5 fill by $0.020 per ounce on entry and stop/market exits, $3.50 round-trip per lot commission and the original project financing model. It holds the MT5 exit decisions fixed. The independent Python strategy run can make different exits. The full unrestricted equity drawdown is stored alongside MT5’s own report drawdown.',
         '',
         'The matched-entry check uses strategy magic, UTC entry minute, direction and within-minute occurrence. Native and Python stop/target decisions can differ inside a session boundary. In the 2026 London long opened May 5 at 12:15 UTC, the static cloned MT5 Tuesday session closed from 21:58 to 23:00 UTC. All 2,073 sub-stop quotes in the probe occurred inside that closure. Python filled its stop at 22:07 and MT5 held the position until a take-profit after reopening. The actual historical Atlas session is unavailable. [Session probe](native_session_probe_20260505.csv)',
         '',
         'Published current Access rules are applied retrospectively. Funded paths include known news restrictions, short-trade deductions, observed Protector liquidations, daily equity resets, trailing floors, inactivity, funded margin checks, 28-day/14-day windows, 3 qualifying $25 days, and the 20% consistency test. The archived news set covers selected USD releases only. Atlas restricts all currencies’ high-impact events. Results and payouts are scenario estimates. No money was paid or received. [Access terms](https://help.atlasfunded.com/access) · [Payout windows](https://help.atlasfunded.com/payouts) · [News rules](https://help.atlasfunded.com/news-trading)',
         '',
         '[Full comparison and event times](native_comparison.csv). The native HTM reports, millisecond deal CSVs, matched-fill CSVs and per-run audit JSONs are in this folder.']
    (ROOT/'native_comparison.md').write_text('\n'.join(txt)+'\n',encoding='utf-8')
    print(len(rows),'audited phase reports')


if __name__=="__main__":
    render()
