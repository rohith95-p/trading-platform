// Native MT5 port of the retained Ultra Core signal functions.
// The chart must use a UTC broker clock and bid OHLC, as in the tested archive.
// Arrays returned by CopyRates are in chronological physical order.
#ifndef RETAINED_NATIVE_SIGNALS_MQH
#define RETAINED_NATIVE_SIGNALS_MQH

datetime RetainedBlock(const datetime scan_time)
{
   return (datetime)((long)scan_time-(long)scan_time%900);
}

datetime RetainedDay(const datetime ts)
{
   return (datetime)((long)ts-(long)ts%86400);
}

double RetainedSLMult(const int magic)
{
   if(magic==7320) return 2.5;
   if(magic==7311) return 3.0;
   if(magic==7324) return 2.0;
   return 0.0;
}

double RetainedTPMult(const int magic)
{
   if(magic==7320) return 3.5;
   if(magic==7311) return 5.0;
   if(magic==7324) return 4.0;
   return 0.0;
}

double RetainedEMA(const double &prices[],const int count,const int period)
{
   double value=0.0;
   for(int i=0;i<period;i++) value+=prices[i];
   value/=period;
   const double alpha=2.0/(period+1);
   for(int i=period;i<count;i++) value=prices[i]*alpha+value*(1.0-alpha);
   return value;
}

// Wilder ATR with a simple-mean seed. The forming bar is synthetic, flat at
// the prior close, so its true range is zero and its ATR is closed ATR * 13/14.
double RetainedClosedATR(const MqlRates &bars[],const int count)
{
   if(count<14) return 0.0;
   double value=0.0;
   for(int i=0;i<count;i++)
   {
      double r=bars[i].high-bars[i].low;
      if(i>0)
         r=MathMax(r,MathMax(MathAbs(bars[i].high-bars[i-1].close),
                             MathAbs(bars[i].low-bars[i-1].close)));
      if(i<14)
      {
         value+=r;
         if(i==13) value/=14.0;
      }
      else value=(value*13.0+r)/14.0;
   }
   return value;
}

MqlRates retained_m15[];
datetime retained_long_block=0;
double retained_long_closed_atr=0.0;

bool RetainedLongView(const datetime scan_time)
{
   const datetime block=RetainedBlock(scan_time);
   if(retained_long_block==block) return true;
   const int count=CopyRates(_Symbol,PERIOD_M15,(datetime)(block-1),7499,retained_m15);
   if(count!=7499 || retained_m15[count-1].time>=block) return false;
   retained_long_closed_atr=RetainedClosedATR(retained_m15,count);
   retained_long_block=block;
   return true;
}

double RetainedATR(const datetime scan_time)
{
   return RetainedLongView(scan_time) ? retained_long_closed_atr*13.0/14.0 : 0.0;
}

datetime retained_short_block=0;
double retained_trail_atr=0.0;
bool retained_consolidates=false;

bool RetainedShortView(const datetime scan_time)
{
   const datetime block=RetainedBlock(scan_time);
   if(retained_short_block==block) return true;
   MqlRates bars[];
   const int count=CopyRates(_Symbol,PERIOD_M15,(datetime)(block-1),19,bars);
   if(count!=19 || bars[count-1].time>=block) return false;
   retained_trail_atr=RetainedClosedATR(bars,19)*13.0/14.0;
   // [-4] within 20 bars is index 16, i.e. ATR through 17 closed bars.
   const double older=RetainedClosedATR(bars,17);
   retained_consolidates=(older>0.0 && (older-retained_trail_atr)/older>0.30);
   retained_short_block=block;
   return true;
}

double RetainedTrailATR(const datetime scan_time)
{
   return RetainedShortView(scan_time) ? retained_trail_atr : 0.0;
}

bool RetainedConsolidates(const datetime scan_time)
{
   return RetainedShortView(scan_time) && retained_consolidates;
}

int RetainedSessionSignal(const int magic,const datetime scan_time)
{
   if(magic!=7320 && magic!=7311 && magic!=7324) return 0;
   const datetime block=RetainedBlock(scan_time);
   const bool london=(magic==7324);
   const int expected=london ? 43200 : 25200;
   if((long)(block-900)%86400!=expected) return 0;
   if(!RetainedLongView(scan_time)) return 0;
   const int last=ArraySize(retained_m15)-1;
   if(retained_m15[last].time!=block-900) return 0;
   const datetime day=RetainedDay(block);
   const datetime from=day+(london ? 25200 : 0);
   const datetime until=day+(london ? 43200 : 21600);
   int first=last;
   while(first>0 && retained_m15[first-1].time>=from) first--;
   double hi=-DBL_MAX,lo=DBL_MAX,closes[24],opens[24];
   int n=0;
   for(int i=first;i<=last && retained_m15[i].time<until;i++)
   {
      if(n>=24) return 0;
      hi=MathMax(hi,retained_m15[i].high);
      lo=MathMin(lo,retained_m15[i].low);
      closes[n]=retained_m15[i].close;
      opens[n]=retained_m15[i].open;
      n++;
   }
   const double width=hi-lo;
   if(!london)
   {
      if(n<10 || width<(magic==7320 ? 3.0 : 5.0)) return 0;
      if(magic==7320)
      {
         const double fraction=width/((hi+lo)/2.0);
         if(fraction<0.003 || fraction>0.016) return 0;
      }
      if(retained_m15[last].close>hi) return 1;
      if(retained_m15[last].close<lo) return -1;
      return 0;
   }
   if(n<16 || retained_long_closed_atr<=0.0 || width<retained_long_closed_atr) return 0;
   const double fast=RetainedEMA(closes,n,8);
   const double slow=RetainedEMA(closes,n,(int)MathMin(21,n));
   int up=0,down=0;
   for(int k=n-4;k<n;k++)
   {
      if(closes[k]>opens[k]) up++;
      if(closes[k]<opens[k]) down++;
   }
   if(fast>slow && up>=3) return 1;
   if(fast<slow && down>=3) return -1;
   return 0;
}

// Construct UTC daily closes from the same M15 history, preserving the short
// Sunday sessions. A platform-specific daily candle merge would change EMA20.
int RetainedD1Bias(const datetime scan_time)
{
   if(!RetainedLongView(scan_time)) return 0;
   const datetime day=RetainedDay(scan_time);
   double closes[49],today_open=0.0;
   int idx=48;
   datetime last_seen=0;
   for(int k=ArraySize(retained_m15)-1;k>=0 && idx>=0;k--)
   {
      const datetime d=RetainedDay(retained_m15[k].time);
      if(d==day) { today_open=retained_m15[k].open; continue; }
      if(d!=last_seen)
      {
         closes[idx--]=retained_m15[k].close;
         last_seen=d;
      }
   }
   if(idx>=0) return 0;
   const double ema=RetainedEMA(closes,49,20);
   const int closed_bias=(closes[48]>ema ? 1 : -1);
   if(today_open<=0.0) return closed_bias;
   const datetime minute=(datetime)((long)scan_time-(long)scan_time%60);
   MqlRates prev[];
   if(CopyRates(_Symbol,PERIOD_M1,(datetime)(minute-1),1,prev)!=1 ||
      prev[0].time<day || prev[0].time>=minute) return closed_bias;
   const double last_close=prev[0].close;
   double delta[14];
   for(int i=0;i<13;i++) delta[i]=MathAbs(closes[36+i]-closes[35+i]);
   delta[13]=MathAbs(last_close-closes[48]);
   ArraySort(delta);
   const double median=(delta[6]+delta[7])/2.0;
   const double move=last_close-today_open;
   if(median>0.0 && MathAbs(move)/median>=1.0) return move>0.0 ? 1 : -1;
   return closed_bias;
}

int RetainedSignal(const int magic,const datetime scan_time)
{
   const int direction=RetainedSessionSignal(magic,scan_time);
   if(direction==0) return 0;
   const int bias=RetainedD1Bias(scan_time);
   return (bias==0 || bias==direction) ? direction : 0;
}
#endif
