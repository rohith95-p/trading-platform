#property strict
#property description "November 21 to December 15 Atlas Access evaluation on one pinned MT5 demo account."

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

const datetime trial_start=D'2026.11.20 18:30:00'; // November 21 at 00:00 IST.
const datetime launch_deadline=D'2026.11.21 18:30:00';
const datetime trial_end=D'2026.12.15 18:30:00'; // December 16 at 00:00 IST.
const double initial=5000.0;
const string attempt_file="UltraCore_AccessNov21_26_attempts.csv";
string state="waiting_for_start", latch_key;
bool started=false;
bool breach_recorded=false;
int attempt=0;
double starting_balance=0., peak=initial, day_anchor=initial;
datetime last_tick=0, last_entry=0, attempt_start=0;
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
             DoubleToString(peak,2),DoubleToString(day_anchor,2),PositionsTotal(),attempt);
   FileClose(file);
}

bool IsBreach()
{
   return state=="daily_loss_breach" || state=="trailing_equity_breach" || state=="inactivity_breach";
}

bool WriteAttemptEvent(const datetime now,const int number,const string event,
                       const double balance,const double equity,const double floor,
                       const datetime started_at)
{
   int file=FileOpen(attempt_file,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE) return false;
   bool ok=FileSeek(file,0,SEEK_END) &&
           FileWrite(file,(long)now,number,event,DoubleToString(balance,2),DoubleToString(equity,2),
                     DoubleToString(floor,2),PositionsTotal(),(long)started_at)>0;
   FileFlush(file);
   FileClose(file);
   return ok;
}

bool FlatConnectedDemo()
{
   return CorrectAccount() && TerminalInfoInteger(TERMINAL_CONNECTED)
      && PositionsTotal()==0 && OrdersTotal()==0 && AccountInfoDouble(ACCOUNT_CREDIT)==0.
      && AccountInfoDouble(ACCOUNT_BALANCE)>0;
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
   if(IsBreach())
   {
      double floor=(state=="daily_loss_breach") ? day_anchor*.95 :
                   (state=="trailing_equity_breach") ? peak*.90 : 0.;
      breach_recorded=WriteAttemptEvent(now,attempt,state,balance,equity,floor,attempt_start);
   }
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

bool BeginAttempt(const datetime now,const bool retry)
{
   int number=attempt+1;
   if(!WriteAttemptEvent(now,number,retry ? "retry_started" : "started",initial,initial,0.,now))
      return false;
   attempt=number;
   attempt_start=now;
   starting_balance=AccountInfoDouble(ACCOUNT_BALANCE);
   peak=initial;
   day_anchor=initial;
   utc_day=-1;
   last_tick=0;
   last_entry=now;
   breach_recorded=false;
   started=true;
   state=retry ? "active" : "awaiting_market";
   return true;
}

void StartEvaluation(const datetime now)
{
   if(state!="waiting_for_start" || now<trial_start) return;
   if(now>=trial_end)
   {
      state="window_complete";
      return;
   }
   if(now>=launch_deadline || !FlatConnectedDemo())
   {
      state="initial_account_state_unverified";
      return;
   }
   if(GlobalVariableSet(latch_key,now)==0)
   {
      state="run_identity_persistence_failed";
      return;
   }
   GlobalVariablesFlush();
   if(!BeginAttempt(now,false)) state="run_identity_persistence_failed";
}

bool AdoptWeekendStart()
{
   if(FileIsExist(attempt_file,FILE_COMMON) || !FlatConnectedDemo()) return false;
   datetime original=(datetime)GlobalVariableGet(latch_key);
   MqlTick tick;
   // Adopt the already-armed run only while there has been no gold quote or account activity.
   if(original<trial_start || original>=launch_deadline || TimeGMT()>=launch_deadline
      || !SymbolInfoTick(_Symbol,tick) || tick.time<=0 || tick.time>=original
      || !HistorySelect(original-1,TimeGMT()) || HistoryDealsTotal()!=0 || HistoryOrdersTotal()!=0)
      return false;
   return BeginAttempt(original,false);
}

void TryRetry(const datetime now)
{
   if(!breach_recorded || !FlatConnectedDemo()
      || MathAbs((long)TimeGMT()-(long)now)>5) return;
   if(!BeginAttempt(now,true)) return;
   first_tick=0;
   previous_minute=(datetime)((long)now/60*60);
   consumed_block=(datetime)((long)now/900*900);
   hard_halt=false;
   anchor_day=-1; week_key=-1; month_key=-1; stop_day=-1;
   realized_day=-1; shutdown_date=-1; losses_today=0; loss_streak=0;
   reference_day=0; reference_week=0; reference_month=0; peak_balance=0; daily_closed=0;
   pause_until=0;
   Status();
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
   latch_key=StringFormat("UltraCore_AccessNov21_26_%I64d",ExpectedDemoLogin);
   if(GlobalVariableCheck(latch_key) && !AdoptWeekendStart())
      state="restart_reconciliation_required";
   StartEvaluation(TimeGMT());
   EventSetTimer(30);
   Status();
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   datetime now=TimeGMT();
   if(CorrectAccount()) StartEvaluation(now);
   if(now>=trial_end && (state=="active" || state=="awaiting_market"))
      state="window_complete";
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
      if(state=="active" || state=="awaiting_market")
      {
         state="window_complete";
         Status();
      }
      return;
   }
   if(IsBreach())
   {
      TryRetry(now);
      return;
   }
   if(state=="awaiting_market")
   {
      if(!TerminalInfoInteger(TERMINAL_CONNECTED) || MathAbs((long)TimeGMT()-(long)now)>5)
         return;
      if(PositionsTotal()!=0 || OrdersTotal()!=0 || AccountInfoDouble(ACCOUNT_CREDIT)!=0.
         || AccountInfoDouble(ACCOUNT_BALANCE)!=starting_balance)
      {
         state="initial_account_state_unverified";
         Status();
         return;
      }
      state="active";
      Status();
   }
   if(!Observe(now)) return;
   int previous=PositionsTotal();
   ResearchTick();
   if(PositionsTotal()>previous) last_entry=now;
}
