#property strict

struct ArchivedRate { long ts; double open, high, low, close; long volume, spread; };
struct ArchivedQuote { long ms; double bid, ask; };

const string symbol="XAUUSDm.L48";
const string folder="RetainedEarly\\";

bool ImportRates(const string month)
{
   int file=FileOpen(folder+month+".rates",FILE_READ|FILE_BIN);
   if(file==INVALID_HANDLE) return false;
   ArchivedRate rows[];
   int count=(int)FileReadArray(file,rows);
   FileClose(file);
   if(count<=0) return false;
   MqlRates rates[];
   if(ArrayResize(rates,count)!=count) return false;
   for(int i=0;i<count;i++)
   {
      rates[i].time=(datetime)rows[i].ts;
      rates[i].open=rows[i].open;
      rates[i].high=rows[i].high;
      rates[i].low=rows[i].low;
      rates[i].close=rows[i].close;
      rates[i].tick_volume=rows[i].volume;
      rates[i].spread=(int)rows[i].spread;
      rates[i].real_volume=0;
   }
   return CustomRatesReplace(symbol,rates[0].time,rates[count-1].time,rates)==count;
}

bool ImportTicks(const string month)
{
   int file=FileOpen(folder+month+".ticks",FILE_READ|FILE_BIN);
   if(file==INVALID_HANDLE) return false;
   ArchivedQuote rows[];
   int count=(int)FileReadArray(file,rows);
   FileClose(file);
   if(count<=0) return false;
   MqlTick ticks[];
   if(ArrayResize(ticks,count)!=count) return false;
   for(int i=0;i<count;i++)
   {
      ticks[i].time_msc=rows[i].ms;
      ticks[i].time=(datetime)(rows[i].ms/1000);
      ticks[i].bid=rows[i].bid;
      ticks[i].ask=rows[i].ask;
      ticks[i].flags=TICK_FLAG_BID|TICK_FLAG_ASK;
      ticks[i].last=0;
      ticks[i].volume=0;
      ticks[i].volume_real=0;
   }
   if(CustomTicksReplace(symbol,ticks[0].time_msc,ticks[count-1].time_msc,ticks)!=count)
      return false;
   Print("RETAINED_IMPORT ",month," ",count);
   return true;
}

void OnStart()
{
   if(!SymbolSelect(symbol,true)) return;
   for(int i=2021*12+8;i<=2022*12+9;i++)
   {
      string month=StringFormat("%04d-%02d",i/12,(i%12)+1);
      if(!ImportRates(month) || (i/12==2022 && !ImportTicks(month)))
      {
         Print("RETAINED_IMPORT_FAILED ",month," ",GetLastError());
         return;
      }
   }
   int file=FileOpen(folder+"complete.txt",FILE_WRITE|FILE_TXT);
   if(file==INVALID_HANDLE) return;
   FileWrite(file,"verified");
   FileClose(file);
}
