#property strict
struct Q { long ms; double b; double a; };
struct R { long ts; double o; double h; double l; double c; long vol; long spr; };
void OnStart(){
 string sym="XAUUSDm.L48",dir="LunaArchive48\\";
 bool custom=false;
 if(!SymbolExist(sym,custom) && !CustomSymbolCreate(sym,"LunaResearch","XAUUSDm")) {Print("LUNA_CREATE_FAILED ",GetLastError());return;}
 if(!SymbolSelect(sym,true)){Print("LUNA_SELECT_FAILED ",GetLastError());return;}
 for(int m=1;m<=50;m++){
   R raw[];MqlRates rates[];
   int f=FileOpen(dir+"rates"+IntegerToString(m)+".bin",FILE_READ|FILE_BIN);
   if(f==INVALID_HANDLE)return;
   int n=(int)FileReadArray(f,raw);FileClose(f);if(n<=0)return;
   ArrayResize(rates,n);
   for(int j=0;j<n;j++){rates[j].time=(datetime)raw[j].ts;rates[j].open=raw[j].o;rates[j].high=raw[j].h;rates[j].low=raw[j].l;rates[j].close=raw[j].c;rates[j].tick_volume=raw[j].vol;rates[j].spread=(int)raw[j].spr;rates[j].real_volume=0;}
   int nr=CustomRatesReplace(sym,rates[0].time,rates[n-1].time,rates);if(nr!=n){Print("LUNA_RATES_FAILED ",m," ",nr,"/",n," ",GetLastError());return;}
   if(m<3)continue;
   Q qs[];MqlTick ticks[];
   f=FileOpen(dir+"ticks"+IntegerToString(m)+".bin",FILE_READ|FILE_BIN);if(f==INVALID_HANDLE)return;
   n=(int)FileReadArray(f,qs);FileClose(f);if(n<=0)return;
   ArrayResize(ticks,n);
   for(int j=0;j<n;j++){ticks[j].time_msc=qs[j].ms;ticks[j].time=(datetime)(qs[j].ms/1000);ticks[j].bid=qs[j].b;ticks[j].ask=qs[j].a;ticks[j].flags=TICK_FLAG_BID|TICK_FLAG_ASK;ticks[j].last=0;ticks[j].volume=0;ticks[j].volume_real=0;}
   int nq=CustomTicksReplace(sym,ticks[0].time_msc,ticks[n-1].time_msc,ticks);if(nq!=n){Print("LUNA_TICKS_FAILED ",m," ",nq,"/",n," ",GetLastError());return;}
   Print("LUNA_IMPORTED ",m," quotes ",n);
 }
 Print("LUNA_IMPORT_COMPLETE");
 int f=FileOpen(dir+"complete.txt",FILE_WRITE|FILE_TXT);FileWrite(f,"complete");FileClose(f);
}
