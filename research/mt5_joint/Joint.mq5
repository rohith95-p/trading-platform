#property strict
#define OnInit RetainedInit
#define OnTick RetainedTick
#define OnTester RetainedExport
#include "RetainedAtlas.mq5"
#undef OnInit
#undef OnTick
#undef OnTester
#include "LunaNotifications.mqh"
input bool CopyLuna=true;
input bool ChartProbe=false;
const long copier_magic=47761;
int cursor=0, blocked_same=0, blocked_opposite=0, ignored_adds=0, accepted=0, max_positions=0;
bool startup=true;
bool pending_close=false;

int OnInit()
{
   if(!PayoutGuard || !MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
   if(ChartProbe)
   {
      ResetLastError();
      long chart=ChartOpen(_Symbol,PERIOD_M5);
      Print("JOINT_CHART_PROBE chart=",chart," error=",GetLastError());
   }
   return RetainedInit();
}

bool CopiedPosition(ulong &ticket)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ticket=PositionGetTicket(i);
      if(ticket && PositionGetInteger(POSITION_MAGIC)==copier_magic) return true;
   }
   return false;
}

void CloseCopy()
{
   ulong ticket=0;
   if(!CopiedPosition(ticket)){pending_close=false; return;}
   orders.SetExpertMagicNumber(copier_magic);
   pending_close=!orders.PositionClose(ticket) || orders.ResultRetcode()!=TRADE_RETCODE_DONE;
   if(pending_close) Print("JOINT_CLOSE_REJECT ",orders.ResultRetcode());
}
void OnTick()
{
   datetime ts=TimeCurrent();
   if(startup)
   {
      while(cursor<ArrayRange(luna_event,0) && luna_event[cursor][0]<ts) cursor++;
      startup=false;
   }
   if(pending_close || (PositionsTotal()>0 && AccountInfoDouble(ACCOUNT_PROFIT)<=-60.)) CloseCopy();
   RetainedTick();
   if(!CopyLuna) return;
   while(cursor<ArrayRange(luna_event,0) && luna_event[cursor][0]<=ts)
   {
      long kind=luna_event[cursor][1], due=luna_event[cursor][0];
      cursor++;
      if(kind==0) {CloseCopy(); continue;}
      if(kind==2) {ignored_adds++; continue;}
      if(kind==3 || ts-due>60) continue;
      if(PositionsTotal()>0)
      {
         ulong occupied=PositionGetTicket(0);
         if(occupied && (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)==(kind>0)) blocked_same++;
         else blocked_opposite++;
         continue;
      }
      if(pending_close || !EligibleRisk(ts) || protector_strikes>=2 || Blackout(ts)) continue;
      MqlTick tick;
      if(!SymbolInfoTick(_Symbol,tick) || tick.ask-tick.bid>350.00001*_Point) continue;
      double price=kind>0 ? tick.ask : tick.bid;
      double sl=NormalizeDouble(price-kind*30.,_Digits),risk=0;
      if(!OrderCalcProfit(kind>0 ? ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,.01,price,sl,risk) || MathAbs(risk)+5.>35.0001) continue;
      orders.SetExpertMagicNumber(copier_magic);
      bool sent=kind>0 ? orders.Buy(.01,_Symbol,0.,sl,0.,"Luna source") : orders.Sell(.01,_Symbol,0.,sl,0.,"Luna source");
      if(sent && orders.ResultRetcode()==TRADE_RETCODE_DONE) accepted++;
      else Print("JOINT_ENTRY_REJECT ",orders.ResultRetcode());
   }
   max_positions=MathMax(max_positions,PositionsTotal());
}
double OnTester()
{
   Print("JOINT_COUNTS accepted=",accepted," same_blocked=",blocked_same," opposite_blocked=",blocked_opposite," ignored_adds=",ignored_adds," max_positions=",max_positions);
   double result=RetainedExport();
   string suffix=IntegerToString((long)first_tick)+"_"+IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE))+".csv";
   string source="JointExport_"+IntegerToString(Mask)+"_"+IntegerToString(Roster)+"_"+suffix;
   FileCopy(source,FILE_COMMON,"JointAtlas_"+IntegerToString(Mask)+"_"+suffix,FILE_COMMON|FILE_REWRITE);
   return result;
}
