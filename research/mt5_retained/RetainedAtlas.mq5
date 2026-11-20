#property strict
#property version "1.00"
#property description "Offline MT5 Strategy Tester research EA for the three retained XAUUSD strategies"
#include <Trade/Trade.mqh>
#include "NativeSignals.mqh"
#include "RetainedNews.mqh"

// Roster 0 is the shared account. The other options run one independent account.
input int Roster=0;
input bool FundedProtector=false;
input bool PayoutGuard=false;
input string RecordID="";
input int Mask=7; // Bit 0 filtered, bit 1 breakout, bit 2 London.

CTrade orders;
const int leg_magic[3]={7320,7311,7324};
const double order_lots=0.02;
datetime first_tick=0, previous_minute=0, consumed_block=0;
bool hard_halt=false, protector_closing=false;
int protector_strikes=0;
int anchor_day=-1, week_key=-1, month_key=-1, stop_day=-1;
int realized_day=-1, shutdown_date=-1, losses_today=0, loss_streak=0;
double reference_day=0, reference_week=0, reference_month=0, peak_balance=0, daily_closed=0;
datetime pause_until=0;

bool RetainedMagic(const long magic)
{
   return magic==7320 || magic==7311 || magic==7324;
}

int ISTDay(const datetime ts) { return (int)(((long)ts+19800)/86400); }

void RollAnchors(const datetime ts, const double balance)
{
   MqlDateTime ist;
   TimeToStruct(ts+19800,ist);
   int day=ISTDay(ts);
   int week=day-(ist.day_of_week+6)%7;
   int month=ist.year*12+ist.mon;
   if(anchor_day!=day) { anchor_day=day; reference_day=balance; losses_today=0; }
   if(week_key!=week) { week_key=week; reference_week=balance; }
   if(month_key!=month) { month_key=month; reference_month=balance; }
   peak_balance=MathMax(peak_balance,balance);
}

bool EligibleRisk(const datetime ts)
{
   double bal=AccountInfoDouble(ACCOUNT_BALANCE),eq=AccountInfoDouble(ACCOUNT_EQUITY);
   RollAnchors(ts,bal);
   if(eq<=0 || bal<50) return false;
   if(eq<=peak_balance*0.70 || eq<=reference_month*0.75) hard_halt=true;
   if(hard_halt || eq<=reference_week*.85 || eq<=reference_day*(bal<400?.97:.94)) return false;
   if(stop_day==ISTDay(ts) || ts<pause_until || (bal<400 && losses_today>=2)) return false;
   if(bal<=reference_week*.85 || bal<=reference_month*.75) return false;
   return AccountInfoDouble(ACCOUNT_MARGIN)/eq<=.20;
}

void OnTradeTransaction(const MqlTradeTransaction &tr,const MqlTradeRequest &req,const MqlTradeResult &res)
{
   if(tr.type!=TRADE_TRANSACTION_DEAL_ADD || tr.deal==0 || !HistoryDealSelect(tr.deal)) return;
   if(HistoryDealGetInteger(tr.deal,DEAL_ENTRY)!=DEAL_ENTRY_OUT) return;
   if(!RetainedMagic(HistoryDealGetInteger(tr.deal,DEAL_MAGIC))) return;
   datetime ts=(datetime)HistoryDealGetInteger(tr.deal,DEAL_TIME);
   long pos=HistoryDealGetInteger(tr.deal,DEAL_POSITION_ID);
   double net=HistoryDealGetDouble(tr.deal,DEAL_PROFIT)+HistoryDealGetDouble(tr.deal,DEAL_SWAP)
             +HistoryDealGetDouble(tr.deal,DEAL_COMMISSION)+HistoryDealGetDouble(tr.deal,DEAL_FEE);
   datetime entry=0;
   if(HistorySelectByPosition(pos))
   {
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong dk=HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(dk,DEAL_ENTRY)==DEAL_ENTRY_IN)
         {
            entry=(datetime)HistoryDealGetInteger(dk,DEAL_TIME);
            net+=HistoryDealGetDouble(dk,DEAL_COMMISSION)+HistoryDealGetDouble(dk,DEAL_FEE);
         }
      }
   }
   int day=ISTDay(ts);
   if(realized_day!=day) { realized_day=day; daily_closed=0; }
   daily_closed+=net;
   // The source live-parity streak counter only sees trades aged at least a minute.
   if(entry==0 || ts-entry<60) return;
   RollAnchors(ts,AccountInfoDouble(ACCOUNT_BALANCE));
   if(net<0)
   {
      loss_streak++; losses_today++;
      if(loss_streak>=5) stop_day=day;
      else if(loss_streak>=3) pause_until=ts+14400;
   }
   else loss_streak=0;
}

bool Blackout(const datetime minute)
{
   for(int i=0;i<ArraySize(retained_news);i++)
      if(MathAbs((long)minute-retained_news[i])<=900) return true;
   return false;
}

void CloseRetained()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || PositionGetString(POSITION_SYMBOL)!=_Symbol || !RetainedMagic(PositionGetInteger(POSITION_MAGIC))) continue;
      orders.SetExpertMagicNumber(PositionGetInteger(POSITION_MAGIC));
      if(!orders.PositionClose(ticket) || orders.ResultRetcode()!=TRADE_RETCODE_DONE)
         Print("RETAINED_CLOSE_REJECT ",ticket," ",orders.ResultRetcode());
   }
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || Roster<0 || Roster>3 || _Period!=PERIOD_M15) return INIT_FAILED;
   if(FundedProtector && AccountInfoInteger(ACCOUNT_LEVERAGE)!=50) return INIT_FAILED;
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return INIT_FAILED;
   orders.SetAsyncMode(false);
   orders.SetTypeFillingBySymbol(_Symbol);
   orders.SetDeviationInPoints(20);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   datetime ts=TimeCurrent();
   datetime minute=(datetime)((long)ts/60*60);
   if(PayoutGuard && PositionsTotal()>0 && AccountInfoDouble(ACCOUNT_PROFIT)<=-60.)
   {
      CloseRetained();
      previous_minute=minute;
      return;
   }
   if(FundedProtector)
   {
      if(!protector_closing && protector_strikes<2 && PositionsTotal()>0
         && AccountInfoDouble(ACCOUNT_EQUITY)-AccountInfoDouble(ACCOUNT_BALANCE)<=-100.)
      {
         protector_strikes++;
         protector_closing=true;
         MqlTick observation;
         SymbolInfoTick(_Symbol,observation);
         Print("RETAINED_PROTECTOR ",protector_strikes," ",observation.time_msc," ",
               DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY)-AccountInfoDouble(ACCOUNT_BALANCE),3));
      }
      if(protector_closing)
      {
         CloseRetained();
         protector_closing=PositionsTotal()>0;
         previous_minute=minute;
         return;
      }
      if(protector_strikes>=2) return;
   }
   if(first_tick==0) first_tick=ts;
   if(minute==previous_minute) return;
   previous_minute=minute;
   MqlDateTime ist;
   TimeToStruct(minute+19800,ist);
   int local_min=ist.hour*60+ist.min;
   bool weekend=ist.day_of_week==6 || ist.day_of_week==0 || (ist.day_of_week==1 && local_min<210);
   if(weekend || (ist.day_of_week==5 && local_min>=1350)) { CloseRetained(); return; }
   if(PositionsTotal()>0 && RetainedConsolidates(minute)) CloseRetained();
   int day=ISTDay(minute);
   if(realized_day!=day) { realized_day=day; daily_closed=0; }
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   if(daily_closed+AccountInfoDouble(ACCOUNT_PROFIT)<=-0.06*balance) shutdown_date=day;
   if(shutdown_date==day) return;
   int utc_min=(int)(((long)minute%86400)/60);
   // Instantaneous edge triggers are only on the last closed 07:00 or 12:00 candle.
   if(!((utc_min>=435 && utc_min<450) || (utc_min>=735 && utc_min<750))) return;
   datetime block=(datetime)((long)minute/900*900);
   if(block==consumed_block || Blackout(minute) || (ist.day_of_week==5 && local_min>=1290)) return;
   if(local_min>=930 && local_min<1050) return; // effective LONDON_NY_OVERLAP after NY_MORNING priority
   if(utc_min<=10 || utc_min>=1430) return;
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q) || q.ask<=0 || q.bid<=0 || (q.ask-q.bid)/_Point>350.00001) return;
   int chosen=0, direction=0;
   for(int i=0;i<3;i++)
   {
      if((Roster!=0 && Roster!=i+1) || (Mask & (1<<i))==0) continue;
      int sig=RetainedSignal(leg_magic[i],minute);
      if(sig!=0) { chosen=leg_magic[i]; direction=sig; break; }
   }
   if(chosen==0) return;
   consumed_block=block;
   if(PositionsTotal()>=3 || !EligibleRisk(minute)) return;
   double atr=RetainedATR(minute);
   if(!MathIsValidNumber(atr) || atr<=0) return;
   double px=direction>0 ? q.ask : q.bid;
   double sl=NormalizeDouble(px-direction*atr*RetainedSLMult(chosen),_Digits);
   double tp=NormalizeDouble(px+direction*atr*RetainedTPMult(chosen),_Digits);
   double lots=PayoutGuard ? .01 : order_lots;
   if(PayoutGuard)
   {
      if(PositionsTotal()>0) return;
      double risk=0.;
      if(!OrderCalcProfit(direction>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,lots,px,sl,risk)
         || MathAbs(risk)+5.>35.) return;
   }
   orders.SetExpertMagicNumber(chosen);
   bool ok=direction>0 ? orders.Buy(lots,_Symbol,0.,sl,tp,"Retained") :
                         orders.Sell(lots,_Symbol,0.,sl,tp,"Retained");
   if(!ok || orders.ResultRetcode()!=TRADE_RETCODE_DONE)
      Print("RETAINED_ENTRY_REJECT ",chosen," ",TimeToString(minute)," ",orders.ResultRetcode());
}

double OnTester()
{
   string fname=(PayoutGuard ? "GuardedAtlas_"+IntegerToString(Mask)+"_" : "RetainedAtlas_")+IntegerToString(Roster)+"_"+IntegerToString((long)first_tick)+"_"+
                IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE))+".csv";
   if(StringLen(RecordID)>0) fname=RecordID+".csv";
   int f=FileOpen(fname,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f==INVALID_HANDLE || !HistorySelect(0,TimeCurrent()+86400)) { Print("RETAINED_EXPORT_ERROR ",GetLastError()); return 0; }
   FileWrite(f,"time_msc","deal","order","position_id","magic","type","entry","volume","price","profit",
             "commission","swap","fee","sl","tp","reason","symbol");
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong d=HistoryDealGetTicket(i);
      long type=HistoryDealGetInteger(d,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      FileWrite(f,HistoryDealGetInteger(d,DEAL_TIME_MSC),d,HistoryDealGetInteger(d,DEAL_ORDER),
                HistoryDealGetInteger(d,DEAL_POSITION_ID),HistoryDealGetInteger(d,DEAL_MAGIC),type,
                HistoryDealGetInteger(d,DEAL_ENTRY),HistoryDealGetDouble(d,DEAL_VOLUME),
                HistoryDealGetDouble(d,DEAL_PRICE),HistoryDealGetDouble(d,DEAL_PROFIT),
                HistoryDealGetDouble(d,DEAL_COMMISSION),HistoryDealGetDouble(d,DEAL_SWAP),
                HistoryDealGetDouble(d,DEAL_FEE),HistoryDealGetDouble(d,DEAL_SL),
                HistoryDealGetDouble(d,DEAL_TP),HistoryDealGetInteger(d,DEAL_REASON),
                HistoryDealGetString(d,DEAL_SYMBOL));
   }
   FileClose(f);
   return TesterStatistics(STAT_PROFIT);
}
