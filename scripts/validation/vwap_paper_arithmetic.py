"""Check published summary arithmetic; does not reconstruct unpublished trades."""
import json
from pathlib import Path


def main():
    # Bhatti SSRN6650958 Tables 3/4; rounded inputs, not observed market trades.
    win_rate,avg_win,avg_loss = .453,2.12,1.07
    buckets = [(70,2.77),(42,1.58),(24,-.07),(111,-1.01)]
    gains = sum(n*r for n,r in buckets if r>0)
    losses = -sum(n*r for n,r in buckets if r<0)
    report = dict(source='https://ssrn.com/abstract=6650958',
        full_text_mirror='https://www.scribd.com/document/1063631287/ssrn-6650958',
        headline_expectancy_R=.414,headline_profit_factor=1.76,
        implied_expectancy_from_summary=win_rate*avg_win-(1-win_rate)*avg_loss,
        implied_pf_from_summary=win_rate*avg_win/((1-win_rate)*avg_loss),
        bucket_count=sum(n for n,_ in buckets),
        implied_expectancy_from_buckets=(gains-losses)/sum(n for n,_ in buckets),
        implied_pf_from_buckets=gains/losses,
        interpretation='Published rounded summaries do not reconcile; no unpublished trade ledger available to resolve definitions. This is not a historical performance verification.')
    Path('research/registry/vwap_paper_arithmetic.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
