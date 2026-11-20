"""Ordered XAUUSD quote audit for original Ultra Core trade ledgers.

The account is reconstructed independently of the signal engine. Fill indices are
global within each month's archive, so duplicate millisecond quotes retain order.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.four_atlas_archive import ticks_for_month
from src.backtesting.costs import SCENARIOS
from src.core.news_filter import TIER1_EVENTS

DAY = 86_400_000
COST = SCENARIOS["realistic_ecn"]


def utc(ms):
    return pd.Timestamp(int(ms), unit="ms", tz="UTC").isoformat()


def known_news():
    path = Path("research/events/usd_high_impact_2022_2026.csv")
    events = list(pd.to_datetime(pd.read_csv(path).scheduled_utc, utc=True))
    for day, rows in TIER1_EVENTS.items():
        events.extend(pd.Timestamp(f"{day} {r['utc_time']}", tz="UTC") for r in rows)
    return np.unique([e.value // 1_000_000 for e in events])


class Account:
    verify_protector_from_quotes = True
    def __init__(self, phase, start, news):
        self.phase = phase
        self.start = self.last_entry = start
        self.status = "active"
        self.finished = None
        self.cash = self.anchor = self.peak = self.min_equity = 5000.
        self.drawdown = self.drawdown_pct = self.max_floating_loss = self.max_margin_ratio = 0.
        self.open = {}
        self.closed = 0
        self.strikes = 0
        self.last_strike_ms = None
        self.entries = 0
        self.missing_sl = 0
        self.day = start // DAY
        self.news = news
        self.deductions = self.cash_paid = 0.
        self.profit_anchor=5000.
        self.first_entry_ms=None
        self.cycle = defaultdict(float)
        self.lifetime = defaultdict(float)
        self.payouts = []
        self.wait_until = self.start + 28*DAY if phase=="funded" else None
        self.events = []
        self.last_bid_ask = None
        self.final_equity = 5000.
        self.overnight_resets = 0

    def end(self, status, ms, equity):
        if self.status == "active":
            self.status = status
            self.finished = utc(ms)
            self.events.append(dict(time=self.finished, event=status, equity=round(float(equity), 6),
                                    balance=round(self.cash, 6), midnight_equity=round(self.anchor, 6),
                                    peak=round(self.peak, 6)))

    def equity(self, day, bid, ask):
        eq = self.cash
        for p in self.open.values():
            ounces = 100*p.lots
            eq = eq + ((bid-p.entry_price) if p.is_buy else (p.entry_price-ask))*ounces
            eq = eq + COST.swap(p.lots, p.is_buy, p.entry_time, day*86400, .001, 100.) - p.commission
        return eq

    def observe(self, q):
        if not len(q) or self.status != "active":
            return
        if not self.open:
            self.last_bid_ask = (q[-1]["bid"], q[-1]["ask"])
            self.final_equity = self.cash
            if self.phase == "unrestricted":
                return
            deadline = self.last_entry+30*DAY
            if deadline <= q[-1]["ms"]:
                self.end("inactivity_breach", deadline, self.cash)
            return
        bids, asks, times = q["bid"], q["ask"], q["ms"]
        e = self.equity(self.day, bids, asks)
        peaks = np.maximum.accumulate(np.maximum(self.peak, e))
        found = []
        margin = sum(p.entry_price*100*p.lots for p in self.open.values())/(50 if self.phase=="funded" else 100)
        ratio = margin/e
        if self.phase != "unrestricted":
            funded = self.phase == "funded"
            checks = [("daily_breach", e < self.anchor*(.97 if funded else .95)),
                      ("trailing_breach", e < peaks*(.94 if funded else .90)),
                      ("inactivity_breach", times >= self.last_entry+30*DAY)]
            if funded:
                if self.verify_protector_from_quotes:
                    checks.append(("protector_requires_liquidation", e-self.cash <= -100))
                checks.append(("margin_requires_liquidation", ratio >= .80))
            for status, mask in checks:
                indices = np.flatnonzero(mask)
                if len(indices):
                    found.append((indices[0],status))
        stop = min(found, key=lambda x:x[0])[0] if found else len(e)-1
        s = slice(0,stop+1)
        self.peak=float(peaks[stop])
        self.min_equity=min(self.min_equity,float(e[s].min()))
        self.drawdown=max(self.drawdown,float((peaks[s]-e[s]).max()))
        self.drawdown_pct=max(self.drawdown_pct,float(((peaks[s]-e[s])/peaks[s]).max())*100)
        self.max_floating_loss=max(self.max_floating_loss,float((self.cash-e[s]).max()))
        self.max_margin_ratio=max(self.max_margin_ratio,float(ratio[s].max()))
        self.final_equity=float(e[stop])
        self.last_bid_ask=(bids[stop],asks[stop])
        if found:
            idx,status=min(found,key=lambda x:x[0])
            ms = int(times[idx])
            if (status == "protector_requires_liquidation" and all(
                    p.exit_reason == "ATLAS_PROTECTOR" and p.exit_time_ms == ms for p in self.open.values())):
                if self.last_strike_ms != ms:
                    self.strikes += 1
                    self.last_strike_ms = ms
                    self.events.append(dict(event="protector_liquidation", strike=self.strikes, time=utc(ms),
                                            equity=float(e[idx]), tickets=[int(k) for k in self.open]))
                if self.strikes>=2:
                    self.end("second_protector_breach",ms,e[idx])
            else:
                self.end(status,ms,e[idx])
                if self.status==status:
                    self.events[-1]["tickets"]=[int(k) for k in self.open]

    def post_cash(self, ms):
        """Check net liquidation and drawdown after a fill at the current quote."""
        if self.last_bid_ask is None:
            raise ValueError("Missing fill quote")
        bid, ask = self.last_bid_ask
        self.final_equity=float(self.equity(self.day,bid,ask))
        self.min_equity=min(self.min_equity,self.final_equity)
        self.peak=max(self.peak,self.final_equity)
        dd=self.peak-self.final_equity
        self.drawdown=max(self.drawdown,dd)
        self.drawdown_pct=max(self.drawdown_pct,100*dd/self.peak)
        self.max_floating_loss=max(self.max_floating_loss,self.cash-self.final_equity)
        if self.phase=="unrestricted":
            return
        if self.final_equity < self.anchor*(.97 if self.phase=="funded" else .95):
            self.end("daily_breach",ms,self.final_equity)
        elif self.final_equity < self.peak*(.94 if self.phase=="funded" else .90):
            self.end("trailing_breach",ms,self.final_equity)

    def advance_day(self, day):
        if self.status != "active":
            return
        if self.phase!="unrestricted" and day*DAY>=self.last_entry+30*DAY:
            self.end("inactivity_breach",self.last_entry+30*DAY,self.final_equity)
            return
        self.day=day
        if self.open:
            self.overnight_resets+=1
            self.anchor=float(self.equity(day,*self.last_bid_ask))
        else:
            self.anchor=self.cash
        if self.phase=="funded":
            self.maybe_pay(day*DAY)

    def maybe_pay(self, ms):
        if self.status!="active" or self.open or self.wait_until is None or ms<self.wait_until:
            return
        if pd.Timestamp(ms,unit="ms",tz="UTC").weekday()>=5:
            return
        profit=sum(self.cycle.values())
        gross=200. if self.strikes else 111.11
        if (self.cash-self.profit_anchor < gross or profit<gross
                or self.qualifying_days()<3
                or max(self.lifetime.values(),default=0.)>.2*profit):
            return
        self.payouts.append(dict(time=utc(ms),gross=gross,modeled_cash=100.))
        self.cash_paid+=100.
        self.cash-=gross
        self.peak=self.profit_anchor=self.cash
        self.anchor-=gross/.97
        self.cycle.clear()
        self.wait_until=ms+14*DAY

    def qualifying_days(self):
        threshold = .005 * self.profit_anchor
        return sum(value >= threshold - 1e-8 for value in self.cycle.values())

    def fill(self, action, p, ms):
        if self.status!="active":
            return
        if action=="entry":
            if self.phase!="unrestricted" and ms>=self.last_entry+30*DAY:
                self.end("inactivity_breach",self.last_entry+30*DAY,self.final_equity)
                return
            self.entries+=1
            self.last_entry = ms
            self.open[p.ticket]=p
            if self.first_entry_ms is None:
                self.first_entry_ms=ms
            self.missing_sl+=int(not (p.initial_sl>0 and np.isfinite(p.initial_sl)))
            if self.phase=="funded" and self.missing_sl>=.8*self.entries:
                self.end("missing_stop_breach",ms,self.final_equity)
                return
            if self.phase=="funded" and np.any(np.abs(self.news-ms)<=300_000) and p.exit_reason!="ATLAS_NEWS":
                self.end("news_entry_requires_liquidation",ms,self.final_equity)
                self.events[-1]["tickets"]=[int(p.ticket)]
                return
        else:
            del self.open[p.ticket]
            self.closed+=1
            net=p.net_pl
            if self.phase=="funded" and (ms-p.entry_time_ms<180_000 or np.any(np.abs(self.news-ms)<=300_000)):
                deduction=max(0.,net)
                if deduction:
                    self.events.append(dict(time=utc(ms),event="profit_deduction",amount=deduction,ticket=int(p.ticket)))
                    self.deductions+=deduction
                    # Atlas excludes deductions from the daily limit. The trailing high-water mark still stands.
                    self.anchor-=deduction/.97
                    net-=deduction
            self.cash+=net
            self.cycle[self.day]+=net
            self.lifetime[self.day]+=net
        self.post_cash(ms)
        if self.phase=="evaluation" and action=="exit" and self.cash>=5150. and self.status=="active":
            self.end("passed",ms,self.final_equity)
        if self.phase=="funded":
            self.maybe_pay(ms)

    def result(self):
        return dict(status=self.status, time=self.finished, entries=self.entries, closes=self.closed,
                    balance=self.cash,equity=self.final_equity, minimum_equity=self.min_equity,
                    first_trade=utc(self.first_entry_ms) if self.first_entry_ms is not None else None,
                    payout_anchor=self.profit_anchor,next_payout_window=utc(self.wait_until) if self.wait_until else None,
                    max_equity_drawdown_usd=self.drawdown, max_equity_drawdown_pct=self.drawdown_pct,
                    max_floating_loss=self.max_floating_loss,max_used_margin_to_equity=self.max_margin_ratio,
                    overnight_resets=self.overnight_resets,peak_equity=self.peak,rule_events=self.events,
                    protector_strikes=self.strikes, qualifying_days=self.qualifying_days(), deductions=self.deductions,
                    modeled_payouts=self.payouts,modeled_cash_received=self.cash_paid)


def run(path):
    cfg=json.loads((path/"summary.json").read_text())
    deals=pd.read_csv(path/"trades.csv")
    result=audit_trade_ledger(cfg,deals)
    (path/"atlas.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


def audit_trade_ledger(cfg, deals, account_type=Account, validate_project_cost=True):
    start,end=cfg["start"]*1000,cfg["end_exclusive"]*1000
    news=known_news()
    accounts=[account_type("unrestricted",start,news),account_type(cfg["phase"],start,news)]
    events=defaultdict(lambda:defaultdict(list))
    for p in deals.itertuples(index=False):
        pl=(p.exit_price-p.entry_price)*(1 if p.is_buy else -1)*p.lots*100
        if validate_project_cost:
            assert abs(pl-p.gross_pl)<1e-7 and abs(pl-p.commission+p.swap-p.net_pl)<1e-7
            assert abs(COST.swap(p.lots,p.is_buy,p.entry_time,p.exit_time,.001,100.)-p.swap)<1e-7
        for action in ("entry","exit"):
            ms=int(getattr(p,action+"_time_ms"))
            month=pd.Timestamp(ms,unit="ms",tz="UTC").strftime("%Y-%m")
            i=int(getattr(p,action+"_quote_index"))
            events[month][i].append((action,p,ms))
    for day in range(start//DAY,(end-1)//DAY+1):
        date=pd.Timestamp(day*DAY,unit="ms",tz="UTC")
        q=ticks_for_month(date.year,date.month)
        low,high=q["ms"].searchsorted([max(day*DAY,start),min((day+1)*DAY,end)])
        for a in accounts:
            if day!=a.day:
                a.advance_day(day)
        left=low
        for i, fills in sorted(events[date.strftime("%Y-%m")].items()):
            if not low<=i<high:
                continue
            for a in accounts:
                a.observe(q[left:i+1])
                # Prior positions may exit, new positions enter, then new positions may exit on this quote.
                for action,p,ms in sorted(fills,key=lambda x: (0 if x[0]=='exit' and x[1].ticket in a.open else 1 if x[0]=='entry' else 2)):
                    assert ms==q['ms'][i]
                    a.fill(action,p,ms)
            left=i+1
        for a in accounts:
            a.observe(q[left:high])
    if accounts[1].status=="active" and end>=accounts[1].last_entry+30*DAY:
        accounts[1].end("inactivity_breach",accounts[1].last_entry+30*DAY,accounts[1].final_equity)
    assert not accounts[0].open and abs(accounts[0].cash-5000-cfg["net"])<1e-5
    result=dict(name=cfg["name"],phase=cfg["phase"],start=utc(start),end_exclusive=utc(end),
                unrestricted=accounts[0].result(),atlas=accounts[1].result(),
                news_coverage="Selected USD releases only; historical Atlas all-currency restrictions unverified.",
                payout_assumption="Request USD 100 cash while flat, normal 90% split (50% after first Protector), immediate settlement and verified KYC assumed; no real payments.")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("directory",type=Path,nargs="+")
    for directory in parser.parse_args().directory:
        r=run(directory)
        print(r["name"],r["phase"],r["atlas"]["status"],r["atlas"]["time"],r["atlas"]["balance"])
