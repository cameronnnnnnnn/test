//+------------------------------------------------------------------+
//|                                           ChallengePhaseV2.mq5    |
//|   FTMO $15k 1-STEP CHALLENGE — tuned for PASS RATE over speed.    |
//|                                                                   |
//|   Research (see challengephasev2/README.md): on NAS100 under      |
//|   FTMO's 3% daily cap, 80%/20-day is structurally impossible      |
//|   (ceiling ~44% in 20d). Relaxing the speed constraint and        |
//|   running to completion lifts the OOS pass rate a lot. This EA    |
//|   ships the chosen frontier spot:                                 |
//|                                                                   |
//|     1.0% risk, 6R, -2R daily circuit breaker, run-to-completion   |
//|     -> ~58-59% pass, ~42% blow, MEDIAN ~13-17 trading days.       |
//|        (drop risk to 0.5% for ~70-77% pass at ~40-53 day median.) |
//|                                                                   |
//|   Setups (CUSUM leg from research was tested + found REDUNDANT,   |
//|   so it is intentionally omitted — VWAP-pullback is the workhorse,|
//|   ORB adds frequency):                                            |
//|     A) US-open ORB : 16:30 server, 15-min range, 50pt stop, 6R,   |
//|        stop->BE after +1R, and only enter >=24 min after the open |
//|        (skips the noisy first breakouts; small OOS WR lift).      |
//|     B) VWAP pullback: buy dips to the US-session VWAP in an       |
//|        uptrend (mirror short), 40pt stop, hard 6R TP, no trail.   |
//|                                                                   |
//|   The -2R breaker STOPS NEW ENTRIES for the day once realized P&L |
//|   is down 2R (= 2*risk%), but LETS OPEN WINNERS RUN (it does not  |
//|   flatten). A separate hard MaxDailyLossPct is a catastrophe-only |
//|   flatten backstop kept just under the 3% FTMO cap.               |
//|                                                                   |
//|   One trade/day per setup; hard TP at the broker, SL moved to BE  |
//|   live for the ORB; flat 22:55 server. REQUIRES A HEDGING ACCOUNT.|
//|   Server time assumed EET/EEST (FTMO). Backtest before live.      |
//+------------------------------------------------------------------+
#property copyright "FTMO research — challenge phase v2"
#property version   "2.00"
#property strict
#include <Trade/Trade.mqh>

input group "=== Risk ==="
input double RiskPercent      = 1.0;    // % balance risked per trade (1.0=fast ~59%/13d; 0.5=safe ~77%/40d)
input double DailyBreakerR    = 2.0;    // halt NEW entries once the day is down this many R (0=off)
input double MaxSpreadPts     = 12.0;   // skip entry if spread wider (index points)

input group "=== Setup A: US-open ORB (server time) ==="
input bool   UseA             = true;
input int    A_Hour           = 16;     // US cash open hour (server EET)
input int    A_Min            = 30;     // 16:30 server
input int    A_ORMinutes      = 15;     // opening-range length
input int    A_MinSinceOpen   = 24;     // only enter >= this many minutes after the open
input double A_StopPoints     = 50.0;
input double A_TP_R           = 6.0;    // hard take-profit (R) — 6R drift to punch +10%
input double A_BE_R           = 1.0;    // move stop to breakeven after +this many R (0=off)

input group "=== Setup B: VWAP trend pullback (US session) ==="
input bool   UseB             = true;
input int    B_SessHour       = 16;     // VWAP session start hour (server) — 16:00
input int    B_SessMin        = 0;
input double B_StopPoints      = 40.0;
input double B_TP_R           = 6.0;    // hard take-profit (R)
input double B_Buf            = 8.0;    // dip within this many points of VWAP
input int    B_TrendBars      = 20;     // VWAP slope lookback (bars)
input int    B_EntryByHour    = 21;     // no new B entries after this hour

input group "=== Session / safety ==="
input int    EODHour          = 22;     // flatten everything after EODHour:EODMin
input int    EODMin           = 55;
input bool   NoFridayEntry    = false;
input double MaxDailyLossPct   = 2.8;   // CATASTROPHE flatten+halt if down this % (keep <3% FTMO cap)
input double HaltBelowEquity  = 0.0;    // flatten+halt while equity <= this $ (0=off; e.g. 13600 on $15k)

input group "=== Misc ==="
input ulong  MagicBase        = 8820000;

CTrade trade;

// per-setup config (filled in OnInit). index 0 = US ORB, 1 = VWAP pullback
double Stop[2];
double TP_R[2];
double BE_R[2];
string Tag[2] = {"A_US_ORB","B_VWPULL"};

bool   g_traded[2];
double g_extreme[2];   // running favourable extreme since entry (for BE)

// ORB state (setup 0)
double g_rHigh, g_rLow;
bool   g_orReady;

// US-session VWAP buffers for Setup B (reset daily)
#define MAXB 800
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB];
int    g_tod[MAXB];
int    g_vc;
double g_cumPV, g_cumV;

datetime g_day = 0;
datetime g_lastBar = 0;
double   g_dayStartEquity  = 0.0;
double   g_dayStartBalance = 0.0;
bool     g_halted = false;       // catastrophe flatten halt (resets next day)
bool     g_noNew  = false;       // -2R breaker: block new entries (resets next day)

//+------------------------------------------------------------------+
int OnInit()
{
   Stop[0]=A_StopPoints; Stop[1]=B_StopPoints;
   TP_R[0]=A_TP_R;       TP_R[1]=B_TP_R;
   BE_R[0]=A_BE_R;       BE_R[1]=0.0;        // pullback is pure hard-TP
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("ChallengePhaseV2 v2.0: risk=%.2f%%  breaker=-%.1fR  A(US ORB)=%d B(VWpull)=%d  catGuard=%.1f%%",
               RiskPercent, DailyBreakerR, UseA, UseB, MaxDailyLossPct);
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

// Opening range for setup 0 from CLOSED bars in [open, open+ORmin).
void ComputeORB(datetime now, int hh, int mm, int orMin)
{
   datetime t0=SessOpen(now,hh,mm), t1=t0+orMin*60;
   if(now<t1) return;
   MqlRates r[];
   int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(orMin*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; }
   if(hi<=lo) return;
   g_rHigh=hi; g_rLow=lo; g_orReady=true;
}

void OpenTrade(int s, int dir, double px)
{
   if(px<=0 || g_noNew) return;                       // breaker blocks new entries
   double lots=LotsFor(Stop[s]); if(lots<=0) return;
   double sl=(dir>0)? px-Stop[s] : px+Stop[s];
   double tp=(TP_R[s]>0)? ((dir>0)? px+TP_R[s]*Stop[s] : px-TP_R[s]*Stop[s]) : 0.0;
   ulong magic=MagicBase+s; trade.SetExpertMagicNumber(magic);
   bool ok=(dir>0)? trade.Buy (lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s])
                  : trade.Sell(lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),NormalizeDouble(tp,_Digits),Tag[s]);
   if(ok){ g_traded[s]=true; g_extreme[s]=px; }
}

// Move stop to breakeven after +BE_R. Preserves the TP. (Setup 0 only; setup 1 BE_R=0.)
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
   // min-since-open filter: only enter once we are >= A_MinSinceOpen minutes past the open
   if(now < SessOpen(now,A_Hour,A_Min)+A_MinSinceOpen*60) { if(!g_orReady) ComputeORB(now,A_Hour,A_Min,A_ORMinutes); return; }
   if(!g_orReady) ComputeORB(now,A_Hour,A_Min,A_ORMinutes);
   if(!g_orReady) return;
   ulong tk; if(SelPos(MagicBase+0,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
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

   // ---- -2R daily circuit breaker: realized day P&L in R-units ----
   if(DailyBreakerR>0 && g_dayStartBalance>0){
      double rUnit=g_dayStartBalance*RiskPercent/100.0;     // 1R in account currency
      if(rUnit>0 && (bal-g_dayStartBalance) <= -DailyBreakerR*rUnit) g_noNew=true;
   }

   // ---- catastrophe guard: flatten + halt (true emergency only) ----
   bool dailyBreach   = (MaxDailyLossPct>0 && g_dayStartEquity>0 &&
                         (eq-g_dayStartEquity)/g_dayStartEquity*100.0 <= -MaxDailyLossPct);
   bool overallBreach = (HaltBelowEquity>0 && eq<=HaltBelowEquity);
   if(dailyBreach) g_halted=true;
   if(g_halted || overallBreach){ for(int s=0;s<2;s++) CloseSetup(s); return; }

   // ---- EOD flatten ----
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){
      for(int s=0;s<2;s++) CloseSetup(s); return;
   }

   // ---- manage open positions every tick (BE for the ORB) ----
   for(int s=0;s<2;s++) ManagePos(s);

   // ---- new closed M1 bar: build US-session VWAP buffers ----
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

   // ---- Setup A: US-open ORB (>=24 min after open) ----
   if(UseA) TryORB(now);

   // ---- Setup B: VWAP trend pullback (on each new closed bar) ----
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
