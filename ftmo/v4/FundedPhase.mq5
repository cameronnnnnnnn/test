//+------------------------------------------------------------------+
//|                                               FundedPhase.mq5     |
//|   FTMO $15k FUNDED phase — converged 3-setup combo                |
//|   (optimized for net banked $/month; see ftmo/v4/FUNDED_RESULTS.md)|
//|                                                                   |
//|   A) US-open ORB  : 16:00 server, 30-min range, 60pt stop, 3R TP, |
//|      volume-confirmed, stop -> BREAKEVEN after +1R.               |
//|   B) EU-open ORB  : 11:00 server, 30-min range, 60pt stop, 3R TP, |
//|      volume-confirmed, stop -> BREAKEVEN after +1R.               |
//|   C) VWAP pullback: buy dips to the US-session VWAP in an uptrend |
//|      (mirror short), 40pt stop, 4R TP, 3R TRAILING stop.          |
//|                                                                   |
//|   One trade/day per setup; hard TP set at entry (broker), SL is   |
//|   trailed/moved to BE live; flat 22:55 server. Risk ~0.67%/trade  |
//|   (3 setups -> <=~2% daily, under FTMO's 3% cap). REQUIRES A      |
//|   HEDGING ACCOUNT. Server time assumed EET/EEST (FTMO).           |
//|                                                                   |
//|   WITHDRAWALS ARE MANUAL: the converged policy is to request a    |
//|   payout on the 14-day cadence and withdraw down to breakeven.    |
//|   This EA only trades; it does not move money. Backtest first.    |
//+------------------------------------------------------------------+
#property copyright "FTMO research — funded phase"
#property version   "1.10"
#property strict
#include <Trade/Trade.mqh>

input group "=== Risk ==="
input double RiskPercent     = 0.67;   // % of balance risked per trade (~$100 on $15k)
input double MaxSpreadPts    = 12.0;   // skip entry if spread wider (index points)

input group "=== Setup A: US-open ORB (server time) ==="
input bool   UseA            = true;
input int    A_Hour          = 16;     // US cash open hour (server EET)
input int    A_Min           = 0;
input int    A_ORMinutes     = 30;     // opening-range length
input double A_StopPoints    = 60.0;
input double A_TP_R          = 3.0;    // hard take-profit (R)
input double A_BE_R          = 1.0;    // move stop to breakeven after +this many R (0=off)
input bool   A_VolFilter     = true;   // require breakout bar volume > OR average

input group "=== Setup B: EU-open ORB (server time) ==="
input bool   UseB            = true;
input int    B_Hour          = 11;     // EU morning (server EET ~= 04:00 ET)
input int    B_Min           = 0;
input int    B_ORMinutes     = 30;
input double B_StopPoints    = 60.0;
input double B_TP_R          = 3.0;
input double B_BE_R          = 1.0;
input bool   B_VolFilter     = true;

input group "=== Setup C: VWAP trend pullback (US session) ==="
input bool   UseC            = true;
input int    C_SessHour      = 16;     // VWAP session start hour (server) = US open
input int    C_SessMin       = 0;
input double C_StopPoints     = 40.0;
input double C_TP_R          = 4.0;    // hard take-profit (R)
input double C_TrailR        = 3.0;    // trailing stop, this many R behind the extreme (0=off)
input double C_Buf           = 8.0;    // dip within this many points of VWAP
input int    C_TrendBars     = 20;     // VWAP slope lookback (bars)
input int    C_EntryByHour   = 21;     // no new C entries after this hour

input group "=== Session / safety ==="
input int    EODHour         = 22;     // flatten everything after EODHour:EODMin
input int    EODMin          = 55;
input bool   NoFridayEntry   = false;
input double MaxDailyLossPct  = 2.5;   // flatten+halt for the day if down this % (0=off; keep <3% FTMO cap)
input double HaltBelowEquity = 0.0;    // flatten+halt while equity <= this $ (0=off; e.g. 13600 on a $15k acct)

input group "=== Misc ==="
input ulong  MagicBase       = 8810000;

CTrade trade;

// per-setup config (filled in OnInit)
double Stop[3];      // stop distance in index points
double TP_R[3];      // hard take-profit in R
double BE_R[3];      // move-to-breakeven trigger in R (0=off)
double TrailR[3];    // trailing stop in R (0=off)
string Tag[3] = {"A_US_ORB","B_EU_ORB","C_VWPULL"};

// per-setup daily state
bool   g_traded[3];
double g_extreme[3];   // running favourable extreme since entry (for BE/trail)

// ORB state for the two ORB setups (index 0=A, 1=B)
double g_rHigh[2], g_rLow[2], g_rVolAvg[2];
bool   g_orReady[2];

// US-session VWAP buffers for Setup C (reset daily)
#define MAXB 800
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB];
int    g_tod[MAXB];
int    g_vc;
double g_cumPV, g_cumV;

datetime g_day = 0;
datetime g_lastBar = 0;
double   g_dayStartEquity = 0.0;
bool     g_halted = false;       // daily-loss halt (resets next day)

//+------------------------------------------------------------------+
int OnInit()
{
   Stop[0]=A_StopPoints; Stop[1]=B_StopPoints; Stop[2]=C_StopPoints;
   TP_R[0]=A_TP_R;       TP_R[1]=B_TP_R;       TP_R[2]=C_TP_R;
   BE_R[0]=A_BE_R;       BE_R[1]=B_BE_R;       BE_R[2]=0.0;
   TrailR[0]=0.0;        TrailR[1]=0.0;        TrailR[2]=C_TrailR;
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("FundedPhase v1.1: risk=%.2f%%  A(US ORB)=%d B(EU ORB)=%d C(VWpull)=%d  dailyGuard=%.1f%%",
               RiskPercent, UseA, UseB, UseC, MaxDailyLossPct);
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

// Compute opening range for ORB setup s (0/1) from CLOSED bars in [open, open+ORmin).
void ComputeORB(int s, datetime now, int hh, int mm, int orMin)
{
   datetime t0=SessOpen(now,hh,mm), t1=t0+orMin*60;
   if(now<t1) return;                       // range window not finished yet
   MqlRates r[];
   int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(orMin*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX, vs=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vs+=(double)r[j].tick_volume; }
   if(hi<=lo) return;
   g_rHigh[s]=hi; g_rLow[s]=lo; g_rVolAvg[s]=vs/n; g_orReady[s]=true;
}

void OpenTrade(int s, int dir, double px)
{
   if(px<=0) return;
   double lots=LotsFor(Stop[s]); if(lots<=0) return;
   double sl=(dir>0)? px-Stop[s] : px+Stop[s];
   double tp=(TP_R[s]>0)? ((dir>0)? px+TP_R[s]*Stop[s] : px-TP_R[s]*Stop[s]) : 0.0;
   ulong magic=MagicBase+s; trade.SetExpertMagicNumber(magic);
   bool ok=(dir>0)? trade.Buy (lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s])
                  : trade.Sell(lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s]);
   if(ok){ g_traded[s]=true; g_extreme[s]=px; }
}

// Move stop to breakeven after +BE_R and/or trail TrailR behind the extreme. Preserves the TP.
void ManagePos(int s)
{
   if(BE_R[s]<=0 && TrailR[s]<=0) return;            // nothing to manage (pure hard TP)
   ulong magic=MagicBase+s, tk; if(!SelPos(magic,tk)) return;
   long type=PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL);
   double curTP=PositionGetDouble(POSITION_TP);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   if(type==POSITION_TYPE_BUY){
      if(bid>g_extreme[s]) g_extreme[s]=bid;
      double newSL=curSL;
      if(TrailR[s]>0)                                   newSL=MathMax(newSL, g_extreme[s]-TrailR[s]*Stop[s]);
      if(BE_R[s]>0 && g_extreme[s]-entry>=BE_R[s]*Stop[s]) newSL=MathMax(newSL, entry);
      if(newSL>curSL+_Point){ trade.SetExpertMagicNumber(magic);
         trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),NormalizeDouble(curTP,_Digits)); }
   } else if(type==POSITION_TYPE_SELL){
      if(g_extreme[s]==0 || ask<g_extreme[s]) g_extreme[s]=ask;
      double newSL=curSL;
      if(TrailR[s]>0){ double t=g_extreme[s]+TrailR[s]*Stop[s]; newSL=(curSL==0)?t:MathMin(newSL,t); }
      if(BE_R[s]>0 && entry-g_extreme[s]>=BE_R[s]*Stop[s]) newSL=(newSL==0)?entry:MathMin(newSL,entry);
      if(curSL==0 || newSL<curSL-_Point){ trade.SetExpertMagicNumber(magic);
         trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),NormalizeDouble(curTP,_Digits)); }
   }
}

// volume confirmation: last CLOSED M1 bar's tick volume above the OR average
bool VolOK(int s)
{
   long vb[]; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vb)!=1) return false;
   return ((double)vb[0] > g_rVolAvg[s]);
}

void TryORB(int s, datetime now, bool useVol, int hh, int mm, int orMin)
{
   if(g_traded[s]) return;
   if(!g_orReady[s]) ComputeORB(s,now,hh,mm,orMin);
   if(!g_orReady[s]) return;
   ulong tk; if(SelPos(MagicBase+s,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(useVol && !VolOK(s)) return;
   if(ask>=g_rHigh[s])     OpenTrade(s,+1,ask);
   else if(bid<=g_rLow[s]) OpenTrade(s,-1,bid);
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);

   // ---- new day reset ----
   datetime ds=DayStart(now);
   if(ds!=g_day){
      g_day=ds; g_vc=0; g_cumPV=0; g_cumV=0; g_halted=false;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
      for(int s=0;s<3;s++){ g_traded[s]=false; g_extreme[s]=0; }
      g_orReady[0]=false; g_orReady[1]=false;
   }

   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=(ask-bid);

   // ---- safety guards: flatten + halt (protect the FTMO daily 3% / overall 10% limits) ----
   bool dailyBreach   = (MaxDailyLossPct>0 && g_dayStartEquity>0 &&
                         (eq-g_dayStartEquity)/g_dayStartEquity*100.0 <= -MaxDailyLossPct);
   bool overallBreach = (HaltBelowEquity>0 && eq<=HaltBelowEquity);
   if(dailyBreach) g_halted=true;
   if(g_halted || overallBreach){ for(int s=0;s<3;s++) CloseSetup(s); return; }

   // ---- EOD flatten ----
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){
      for(int s=0;s<3;s++) CloseSetup(s); return;
   }

   // ---- manage open positions every tick (BE / trail) ----
   for(int s=0;s<3;s++) ManagePos(s);

   // ---- new closed M1 bar: build US-session VWAP buffers ----
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   bool newBar=(bt!=g_lastBar);
   if(newBar){
      g_lastBar=bt;
      if(bt>=SessOpen(now,C_SessHour,C_SessMin) && g_vc<MAXB){
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

   bool canEnter = !(NoFridayEntry && st.day_of_week==5) && (spread<=MaxSpreadPts);
   if(!canEnter) return;

   // ---- Setup A: US-open ORB (evaluate every tick once range is ready) ----
   if(UseA) TryORB(0,now,A_VolFilter,A_Hour,A_Min,A_ORMinutes);
   // ---- Setup B: EU-open ORB ----
   if(UseB) TryORB(1,now,B_VolFilter,B_Hour,B_Min,B_ORMinutes);

   // ---- Setup C: VWAP trend pullback (evaluate on each new closed bar) ----
   if(UseC && newBar && !g_traded[2] && g_vc>C_TrendBars){
      int j=g_vc-1;
      if(g_tod[j] <= C_EntryByHour*60){
         double vw=g_vwap[j];
         bool up = (g_close[j]>vw && vw>g_vwap[j-C_TrendBars]);
         bool dn = (g_close[j]<vw && vw<g_vwap[j-C_TrendBars]);
         if(up && g_low[j]<=vw+C_Buf && g_close[j]>vw)        OpenTrade(2,+1,ask);
         else if(dn && g_high[j]>=vw-C_Buf && g_close[j]<vw)  OpenTrade(2,-1,bid);
      }
   }
}
//+------------------------------------------------------------------+
