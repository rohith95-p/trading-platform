#property strict
#property description "December 2026 Atlas Access evaluation on one pinned MT5 demo account."

bool DecemberEntryAllowed(const double lots,const double price);
#define RETAINED_PRE_ENTRY(lots,price) DecemberEntryAllowed(lots,price)
#define RETAINED_DEFAULT_MASK 5
#define OnInit ResearchInit
#define OnTick ResearchTick
#define OnTester ResearchExport
#include "RetainedAtlas.mq5"
#undef OnInit
#undef OnTick
#undef OnTester

input long ExpectedDemoLogin=0;
input string ExpectedDemoServer="";

const datetime trial_start=D'2026.12.01 00:00:00';
const datetime trial_end=D'2027.01.01 00:00:00';
const double initial=5000.0;
string state="waiting_for_december", latch_key;
bool started=false;
double starting_balance=0., peak=initial, day_anchor=initial;
datetime last_tick=0, last_entry=0;
int utc_day=-1;

bool CorrectAccount()
{
   return ExpectedDemoLogin>0 && StringLen(ExpectedDemoServer)>0
      && AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO
      && AccountInfoInteger(ACCOUNT_LOGIN)==ExpectedDemoLogin
      && AccountInfoString(ACCOUNT_SERVER)==ExpectedDemoServer
      && AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
      && AccountInfoString(ACCOUNT_CURRENCY)=="USD";
}

void Status()
{
   int file=FileOpen("UltraCore_December2026_status.csv",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(file==INVALID_HANDLE) return;
   FileWrite(file,TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS),state,
             DoubleToString(started ? initial+AccountInfoDouble(ACCOUNT_BALANCE)-starting_balance : initial,2),
             DoubleToString(peak,2),DoubleToString(day_anchor,2),PositionsTotal());
   FileClose(file);
}

bool Observe(const datetime now)
{
   if(!CorrectAccount())
   {
      state="account_identity_refused";
      return false;
   }
   if(now<trial_start || now>=trial_end || state!="active") return false;
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)
      || MathAbs((long)TimeGMT()-(long)now)>5) return false;
   double equity=initial+AccountInfoDouble(ACCOUNT_EQUITY)-starting_balance;
   double balance=initial+AccountInfoDouble(ACCOUNT_BALANCE)-starting_balance;
   if(!MathIsValidNumber(equity) || !MathIsValidNumber(balance)) return false;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!PositionGetTicket(i) || PositionGetString(POSITION_SYMBOL)!=_Symbol
         || (PositionGetInteger(POSITION_MAGIC)!=7320 && PositionGetInteger(POSITION_MAGIC)!=7324))
      {
         state="foreign_position_refused";
         Status();
         return false;
      }
   }
   if(OrdersTotal()!=0)
   {
      state="pending_orders_refused";
      Status();
      return false;
   }
   int day=(int)((long)now/86400);
   if(day!=utc_day)
   {
      if(PositionsTotal()!=0 && (last_tick+1<now || now%86400>1))
      {
         state="midnight_equity_unverified";
         Status();
         return false;
      }
      day_anchor=equity;
      utc_day=day;
   }
   last_tick=now;
   peak=MathMax(peak,equity);
   if(equity<day_anchor*.95) state="daily_loss_breach";
   else if(equity<peak*.90) state="trailing_equity_breach";
   else if(now-last_entry>=30*86400) state="inactivity_breach";
   else if(balance>=initial*1.03) state="evaluation_passed";
   if(state=="active") return true;
   Status();
   Print("DECEMBER_ACCESS ",state);
   return false;
}

bool DecemberEntryAllowed(const double lots,const double price)
{
   if(!Observe(TimeCurrent()) || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)
      || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return false;
   double volume=lots;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(!PositionGetTicket(i)) return false;
      volume+=PositionGetDouble(POSITION_VOLUME);
   }
   double equity=initial+AccountInfoDouble(ACCOUNT_EQUITY)-starting_balance;
   // Demo broker leverage may differ. Admission uses the tested 1:100 evaluation.
   return volume*price*100.0/100.0<equity;
}

int OnInit()
{
   if(MQLInfoInteger(MQL_TESTER) || !CorrectAccount() || _Symbol!="XAUUSDm"
      || _Period!=PERIOD_M15 || Roster!=0 || Mask!=5 || PayoutGuard || FundedProtector)
      return INIT_FAILED;
   if(MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE)-100.0)>1e-9 || _Digits!=3
      || MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-.01)>1e-9
      || MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP)-.01)>1e-9)
      return INIT_FAILED;
   orders.SetAsyncMode(false);
   orders.SetTypeFillingBySymbol(_Symbol);
   orders.SetDeviationInPoints(20);
   latch_key=StringFormat("UltraCore_Dec26_%I64d",ExpectedDemoLogin);
   if(GlobalVariableCheck(latch_key)) state="restart_reconciliation_required";
   EventSetTimer(30);
   Status();
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   if(started && state=="active" && PositionsTotal()>0 && !TerminalInfoInteger(TERMINAL_CONNECTED))
      state="exposure_during_connection_loss";
   Status();
}

void OnTick()
{
   datetime now=TimeCurrent();
   if(!CorrectAccount() || now<trial_start) return;
   if(now>=trial_end)
   {
      if(state=="active")
      {
         state="window_complete";
         Status();
      }
      return;
   }
   if(!started && state=="waiting_for_december")
   {
      if(now-trial_start>60 || MathAbs((long)TimeGMT()-(long)now)>5
         || PositionsTotal()!=0 || OrdersTotal()!=0
         || AccountInfoDouble(ACCOUNT_CREDIT)!=0. || GlobalVariableCheck(latch_key))
      {
         state="initial_account_state_unverified";
         Status();
         return;
      }
      if(GlobalVariableSet(latch_key,now)==0)
      {
         state="run_identity_persistence_failed";
         Status();
         return;
      }
      GlobalVariablesFlush();
      starting_balance=AccountInfoDouble(ACCOUNT_BALANCE);
      last_entry=trial_start;
      started=true;
      state="active";
   }
   if(!Observe(now)) return;
   int previous=PositionsTotal();
   ResearchTick();
   if(PositionsTotal()>previous) last_entry=now;
}
