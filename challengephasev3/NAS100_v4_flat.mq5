//+------------------------------------------------------------------+
//|                                            NAS100_v4_flat.mq5     |
//|   FTMO $15k 1-Step CHALLENGE — your LIVE strategy, UNCHANGED,     |
//|   with ONE fix: an end-of-day flatten at 22:55 so no trade ever   |
//|   carries overnight / over the weekend.                           |
//|                                                                   |
//|   WHY: the backtest that all the pass-rate numbers come from      |
//|   closes every trade at the 22:55 session end. The old EA did NOT |
//|   flatten, so ~16% of trades (the ones that don't hit TP/SL in    |
//|   session) were held overnight — paying swap and taking weekend   |
//|   GAP risk that the model never accounted for (stops don't stop   |
//|   gaps). This version matches the tested behaviour exactly.       |
//|                                                                   |
//|   STRATEGY IS IDENTICAL to what you run (so all analysis holds):  |
//|     A_ORB : US open 16:00 server, 15-min range, 50pt stop, 4R TP, |
//|             volume-confirmed breakout, no BE, both directions.    |
//|     B_PULL: buy dips to the US-session VWAP in an uptrend (mirror |
//|             short), 40pt stop, hard 4R TP, no trail/BE.           |
//|   1 trade/day per setup, 1.0% risk each, hard SL+TP at the broker.|
//|                                                                   |
//|   The 22:55 flatten is the only always-on change. The daily       |
//|   breaker and catastrophe guard are OPTIONAL and default OFF so   |
//|   this is a faithful drop-in. REQUIRES A HEDGING ACCOUNT. Server  |
//|   time assumed EET/EEST (FTMO). Backtest in the Strategy Tester   |
//|   before going live.                                              |
//+------------------------------------------------------------------+
#property copyright "FTMO research — challenge live, EOD-flatten fix"
#property version   "4.10"
#property strict
#include <Trade/Trade.mqh>

input group "=== Risk ==="
input double RiskPercent      = 1.0;    // % balance risked per trade (your live setting)
input double MaxSpreadPts     = 12.0;   // skip entry if spread wider (index points)

input group "=== Setup A: A_ORB (US open, server time) ==="
input bool   UseA             = true;
input int    A_Hour           = 16;     // US open hour (server EET) — your live 16:00
input int    A_Min            = 0;
input int    A_ORMinutes      = 15;     // opening-range length
input double A_StopPoints     = 50.0;
input double A_TP_R           = 4.0;    // hard take-profit (R)
input double A_BE_R           = 0.0;    // move stop to BE after +this many R (0=off, your live)
input bool   A_VolFilter      = true;   // require breakout-bar volume > OR average

input group "=== Setup B: B_PULL (VWAP trend pullback) ==="
input bool   UseB             = true;
input int    B_SessHour       = 16;     // VWAP session start hour (server) — 16:00
input int    B_SessMin        = 0;
input double B_StopPoints      = 40.0;
input double B_TP_R           = 4.0;    // hard take-profit (R)
input double B_Buf            = 8.0;    // dip within this many points of VWAP
input int    B_TrendBars      = 20;     // VWAP slope lookback (bars)
input int    B_EntryByHour    = 21;     // no new B entries after this hour

input group "=== Session / safety ==="
input int    EODHour          = 22;     // *** THE FIX *** flatten everything after EODHour:EODMin
input int    EODMin           = 55;     // 22:55 server = the backtest's session end (no overnight/weekend holds)
input bool   NoFridayEntry    = false;  // optional: skip Friday entries (avoids weekend carry entirely)
input double DailyBreakerR    = 0.0;    // optional: halt NEW entries once day down this many R (0=off)
input double MaxDailyLossPct  = 0.0;    // optional catastrophe flatten+halt if down this % (0=off; e.g. 2.8)
input double HaltBelowEquity  = 0.0;    // optional: flatten+halt while equity <= this $ (0=off)

input group "=== Misc ==="
input ulong  MagicBase        = 8830000;

CTrade trade;

// per-setup config. index 0 = A_ORB, 1 = B_PULL
double Stop[2]; double TP_R[2]; double BE_R[2];
string Tag[2] = {"A_ORB","B_PULL"};

bool   g_traded[2];
double g_extreme[2];

// ORB state (setup 0)
double g_rHigh, g_rLow, g_rVolAvg;
bool   g_orReady;

// US-session VWAP buffers (setup 1)
#define MAXB 800
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB];
int    g_tod[MAXB];
int    g_vc; double g_cumPV, g_cumV;

datetime g_day = 0;
datetime g_lastBar = 0;
double   g_dayStartEquity  = 0.0;
double   g_dayStartBalance = 0.0;
bool     g_halted = false;      // catastrophe halt
bool     g_noNew  = false;      // -XR breaker (optional)

//+------------------------------------------------------------------+
int OnInit()
{
   Stop[0]=A_StopPoints; Stop[1]=B_StopPoints;
   TP_R[0]=A_TP_R;       TP_R[1]=B_TP_R;
   BE_R[0]=A_BE_R;       BE_R[1]=0.0;
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("NAS100_v4_flat v4.1: risk=%.2f%%  A_ORB=%d B_PULL=%d  EOD-flatten=%02d:%02d  breaker=-%.1fR",
               RiskPercent, UseA, UseB, EODHour, EODMin, DailyBreakerR);
   return(INIT_SUCCEEDED);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
datetime SessOpen(datetime t,int hh,int mm){ MqlDateTime s; TimeToStruct(t,s); s.hour=hh;s.min=mm;s.sec=0; return StructToTime(s); }

double LotsFor(double stop_pts)
{
   double riskMon=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0||stop_pts<=0) return 0.0;
   double lpl=(stop_pts/ts)*tv; if(lpl<=0) return 0.0;
   double lots=riskMon/lpl;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   if(lots<mn)lots=mn; if(lots>mx)lots=mx;
   return lots;
}

bool SelPos(ulong magic, ulong &ticket)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && PositionGetString(POSITION_SYMBOL)==_Symbol
         && (ulong)PositionGetInteger(POSITION_MAGIC)==magic){ ticket=tk; return true; }
   }
   return false;
}

void CloseSetup(int s)
{
   ulong tk; if(SelPos(MagicBase+s,tk)){ trade.SetExpertMagicNumber(MagicBase+s); trade.PositionClose(tk); }
}

void ComputeORB(datetime now, int hh, int mm, int orMin)
{
   datetime t0=SessOpen(now,hh,mm), t1=t0+orMin*60;
   if(now<t1) return;
   MqlRates r[];
   int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(orMin*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX, vs=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vs+=(double)r[j].tick_volume; }
   if(hi<=lo) return;
   g_rHigh=hi; g_rLow=lo; g_rVolAvg=vs/n; g_orReady=true;
}

bool VolOK()
{
   long vb[]; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vb)!=1) return false;
   return ((double)vb[0] > g_rVolAvg);
}

void OpenTrade(int s, int dir, double px)
{
   if(px<=0 || g_noNew) return;
   double lots=LotsFor(Stop[s]); if(lots<=0) return;
   double sl=(dir>0)? px-Stop[s] : px+Stop[s];
   double tp=(TP_R[s]>0)? ((dir>0)? px+TP_R[s]*Stop[s] : px-TP_R[s]*Stop[s]) : 0.0;
   ulong magic=MagicBase+s; trade.SetExpertMagicNumber(magic);
   bool ok=(dir>0)? trade.Buy (lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s])
                  : trade.Sell(lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s]);
   if(ok){ g_traded[s]=true; g_extreme[s]=px; }
}

// optional breakeven (only if BE_R>0; your live has it 0 -> no-op). Preserves TP.
void ManagePos(int s)
{
   if(BE_R[s]<=0) return;
   ulong magic=MagicBase+s, tk; if(!SelPos(magic,tk)) return;
   long type=PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL);
   double curTP=PositionGetDouble(POSITION_TP);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(type==POSITION_TYPE_BUY){
      if(bid>g_extreme[s]) g_extreme[s]=bid;
      if(g_extreme[s]-entry>=BE_R[s]*Stop[s] && curSL<entry-_Point){
         trade.SetExpertMagicNumber(magic);
         trade.PositionModify(tk,NormalizeDouble(entry,_Digits),NormalizeDouble(curTP,_Digits)); }
   } else if(type==POSITION_TYPE_SELL){
      if(g_extreme[s]==0 || ask<g_extreme[s]) g_extreme[s]=ask;
      if(entry-g_extreme[s]>=BE_R[s]*Stop[s] && (curSL==0 || curSL>entry+_Point)){
         trade.SetExpertMagicNumber(magic);
         trade.PositionModify(tk,NormalizeDouble(entry,_Digits),NormalizeDouble(curTP,_Digits)); }
   }
}

void TryORB(datetime now)
{
   if(g_traded[0]) return;
   if(!g_orReady) ComputeORB(now,A_Hour,A_Min,A_ORMinutes);
   if(!g_orReady) return;
   ulong tk; if(SelPos(MagicBase+0,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(A_VolFilter && (ask>=g_rHigh || bid<=g_rLow) && !VolOK()) return;   // need volume on the breakout
   if(ask>=g_rHigh)     OpenTrade(0,+1,ask);
   else if(bid<=g_rLow) OpenTrade(0,-1,bid);
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);

   // ---- new day reset ----
   datetime ds=DayStart(now);
   if(ds!=g_day){
      g_day=ds; g_vc=0; g_cumPV=0; g_cumV=0; g_halted=false; g_noNew=false;
      g_dayStartEquity =AccountInfoDouble(ACCOUNT_EQUITY);
      g_dayStartBalance=AccountInfoDouble(ACCOUNT_BALANCE);
      for(int s=0;s<2;s++){ g_traded[s]=false; g_extreme[s]=0; }
      g_orReady=false;
   }

   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=(ask-bid);

   // ---- optional -XR daily breaker (block new entries) ----
   if(DailyBreakerR>0 && g_dayStartBalance>0){
      double rUnit=g_dayStartBalance*RiskPercent/100.0;
      if(rUnit>0 && (bal-g_dayStartBalance) <= -DailyBreakerR*rUnit) g_noNew=true;
   }

   // ---- optional catastrophe guard (flatten + halt) ----
   bool dailyBreach   = (MaxDailyLossPct>0 && g_dayStartEquity>0 &&
                         (eq-g_dayStartEquity)/g_dayStartEquity*100.0 <= -MaxDailyLossPct);
   bool overallBreach = (HaltBelowEquity>0 && eq<=HaltBelowEquity);
   if(dailyBreach) g_halted=true;
   if(g_halted || overallBreach){ for(int s=0;s<2;s++) CloseSetup(s); return; }

   // ---- *** THE FIX: end-of-day flatten (also flattens Friday -> no weekend carry) *** ----
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){
      for(int s=0;s<2;s++) CloseSetup(s); return;
   }

   // ---- manage open positions (optional BE only) ----
   for(int s=0;s<2;s++) ManagePos(s);

   // ---- build US-session VWAP buffers on each new closed M1 bar ----
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   bool newBar=(bt!=g_lastBar);
   if(newBar){
      g_lastBar=bt;
      if(bt>=SessOpen(now,B_SessHour,B_SessMin) && g_vc<MAXB){
         double bh=iHigh(_Symbol,PERIOD_M1,1), bl=iLow(_Symbol,PERIOD_M1,1), bc=iClose(_Symbol,PERIOD_M1,1);
         double bv=(double)iVolume(_Symbol,PERIOD_M1,1);
         double tpx=(bh+bl+bc)/3.0;
         g_cumPV+=tpx*bv; g_cumV+=bv;
         double vw=(g_cumV>0)?g_cumPV/g_cumV:bc;
         MqlDateTime bs; TimeToStruct(bt,bs);
         int j=g_vc;
         g_vwap[j]=vw; g_close[j]=bc; g_low[j]=bl; g_high[j]=bh; g_tod[j]=bs.hour*60+bs.min;
         g_vc++;
      }
   }

   bool canEnter = !g_noNew && !(NoFridayEntry && st.day_of_week==5) && (spread<=MaxSpreadPts);
   if(!canEnter) return;

   // ---- Setup A: A_ORB ----
   if(UseA) TryORB(now);

   // ---- Setup B: B_PULL (VWAP trend pullback, on each new closed bar) ----
   if(UseB && newBar && !g_traded[1] && g_vc>B_TrendBars){
      int j=g_vc-1;
      if(g_tod[j] <= B_EntryByHour*60){
         double vw=g_vwap[j];
         bool up = (g_close[j]>vw && vw>g_vwap[j-B_TrendBars]);
         bool dn = (g_close[j]<vw && vw<g_vwap[j-B_TrendBars]);
         if(up && g_low[j]<=vw+B_Buf && g_close[j]>vw)        OpenTrade(1,+1,ask);
         else if(dn && g_high[j]>=vw-B_Buf && g_close[j]<vw)  OpenTrade(1,-1,bid);
      }
   }
}
//+------------------------------------------------------------------+
