#property strict
#property description "Read-only native Strategy Tester session and tick probe (5 May 2026)"
long seen=0,below=0,far_below=0,first_below=0,last_below=0;
double low=DBL_MAX;
int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
   return INIT_SUCCEEDED;
}
void OnTick()
{
   datetime sec=TimeCurrent();
   if(sec<D'2026.05.05 21:00' || sec>=D'2026.05.05 23:58') return;
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q)) return;
   seen++;
   low=MathMin(low,q.bid);
   if(q.bid<=4549.812)
   {
      below++;
      if(first_below==0) first_below=q.time_msc;
      last_below=q.time_msc;
      if(q.bid<4549.) far_below++;
   }
}
double OnTester()
{
   int f=FileOpen("RetainedSessionProbe20260505.csv",FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,',');
   if(f==INVALID_HANDLE) return 0;
   FileWrite(f,"kind","weekday","index","from","until");
   for(int day=0;day<7;day++)
   {
      datetime a=0,b=0;
      for(uint i=0;SymbolInfoSessionTrade(_Symbol,(ENUM_DAY_OF_WEEK)day,i,a,b);i++)
         FileWrite(f,"trade",day,i,(long)a,(long)b);
      for(uint i=0;SymbolInfoSessionQuote(_Symbol,(ENUM_DAY_OF_WEEK)day,i,a,b);i++)
         FileWrite(f,"quote",day,i,(long)a,(long)b);
   }
   FileWrite(f,"ticks",seen,"minimum_bid",low);
   FileWrite(f,"at_or_below_native_stop",below,"first_ms",first_below,"last_ms",last_below);
   FileWrite(f,"below_4549",far_below);
   FileClose(f);
   return (double)below;
}
