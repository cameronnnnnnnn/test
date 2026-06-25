//+------------------------------------------------------------------+
//|                                              NAS100_combo.mq5     |
//|   FTMO $15k 1-Step — 3-setup SCALE-OUT combo (validated v2)       |
//|                                                                   |
//|   A) US Opening-Range Breakout : 16:00 server, 15m range, 50pt    |
//|      stop, volume-confirmed. Scale 2/3 out at +2R; runner -> BE   |
//|      + trail 3R.                                                  |
//|   B) VWAP trend-PULLBACK       : buy dips to session VWAP in an   |
//|      uptrend (mirror short), 40pt stop. Scale 1/2 at +2R; BE+trail3|
//|   C) SELECTIVE range-FADE      : only when VWAP is flat (range    |
//|      day), fade >2 sigma stretch back to VWAP, 40pt stop. Scale   |
//|      1/2 at +1R; runner -> BE + trail 2R.                         |
//|                                                                   |
//|   One trade/day per setup, US cash session, flat 22:55 server, no |
//|   Friday entries. Risk 1.0%/trade: 3 trades/day -> 3 stops stay   |
//|   under the 3% daily cap. REQUIRES A HEDGING ACCOUNT.             |
//|   Server time assumed EET/EEST (FTMO). Backtest before live.      |
//+------------------------------------------------------------------+
#property copyright "FTMO research v2"
#property version   "2.00"
#property strict
#include <Trade/Trade.mqh>

input group "=== Session (server time, EET/EEST) ==="
input int    OpenHour     = 16;    // US cash open hour (server)
input int    OpenMin      = 0;     // open minute
input int    ORMinutes    = 15;    // Setup A opening-range length
input int    EntryByHour  = 21;    // no new B/C entries after this hour
input int    EODHour      = 22;    // flatten after EODHour:EODMin
input int    EODMin       = 55;
input bool   NoFridayEntry= false;   // Fridays HELP this EOD-flat strat (4wk pass 81% vs 68% without); keep them on

input group "=== Risk ==="
input double RiskPercent  = 1.0;   // % per trade (1R). KEEP <=1.0: 3 trades/day vs 3% daily cap
input double MaxSpreadPts = 12.0;  // skip entry if spread wider (index points)

input group "=== Setup toggles ==="
input bool   UseA_ORB      = true;
input bool   UseB_Pullback = true;
input bool   UseC_Fade     = false;  // fade leg is a net drag once losses are booked at -1R; off
input bool   UseScaleOut   = false;  // OFF = trail-only (the real edge lives in the fat tail)

input group "=== Fade (Setup C) tuning ==="
input double FadeZ         = 2.0;  // sigma stretch to fade
input double FadeFlatPts   = 15.0; // |VWAP slope over 40 bars| below this = range day

input group "=== Misc ==="
input ulong  MagicBase     = 8800000;

CTrade trade;

// per-setup fixed, validated params:           A(ORB)  B(pull)  C(fade)
double Stop[3]     = {50.0, 40.0, 40.0};
double PartR[3]    = { 2.0,  2.0,  1.0};
double PartFrac[3] = {0.67,  0.5,  0.5};
double TrailR[3]   = { 3.0,  3.0,  2.0};

// per-setup daily state
bool   g_traded[3];
bool   g_partDone[3];
double g_extreme[3];

// ORB (Setup A) state
double g_rHigh, g_rLow, g_rVolAvg;
bool   g_orReady;

// session VWAP buffers (reset daily at open)
#define MAXB 700
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB], g_dev[MAXB];
int    g_tod[MAXB];
int    g_vc;
double g_cumPV, g_cumV;
datetime g_day = 0;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("NAS100_combo v2: risk=%.2f%% setups A=%d B=%d C=%d", RiskPercent,
               UseA_ORB, UseB_Pullback, UseC_Fade);
   return(INIT_SUCCEEDED);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
datetime TodayOpen(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=OpenHour;s.min=OpenMin;s.sec=0; return StructToTime(s); }

double LotsForRisk()
{
   double riskMon=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0) return 0.0;
   // value of a 1R (Stop[0]-agnostic): caller scales by its own stop, so compute per-point here
   return riskMon; // returns risk money; lots computed per setup
}

double LotsFor(double stop_pts)
{
   double riskMon=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0) return 0.0;
   double lpl=(stop_pts/ts)*tv; if(lpl<=0) return 0.0;
   double lots=riskMon/lpl;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   lots=MathFloor(lots/step)*step; if(lots<mn)lots=mn; if(lots>mx)lots=mx;
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

double StdDevDev(int endIdx, int win)
{
   if(endIdx-win+1<0) return 0.0;
   double m=0; for(int i=endIdx-win+1;i<=endIdx;i++) m+=g_dev[i]; m/=win;
   double v=0; for(int i=endIdx-win+1;i<=endIdx;i++){ double d=g_dev[i]-m; v+=d*d; } v/=win;
   return MathSqrt(v);
}

void ComputeORB(datetime now)
{
   datetime t0=TodayOpen(now), t1=t0+ORMinutes*60;
   if(now<t1) return;
   MqlRates r[];
   int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(ORMinutes*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX, vs=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vs+=(double)r[j].tick_volume; }
   if(hi<=lo) return;
   g_rHigh=hi; g_rLow=lo; g_rVolAvg=vs/n; g_orReady=true;
}

void OpenTrade(int s, int dir, double px)
{
   double lots=LotsFor(Stop[s]); if(lots<=0) return;
   double sl = (dir>0)? px-Stop[s] : px+Stop[s];
   ulong magic=MagicBase+s;
   trade.SetExpertMagicNumber(magic);
   string cm=(s==0?"A_ORB":(s==1?"B_PULL":"C_FADE"));
   bool ok = (dir>0)? trade.Buy(lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),0.0,cm)
                    : trade.Sell(lots,_Symbol,0.0,NormalizeDouble(sl,_Digits),0.0,cm);
   if(ok){ g_traded[s]=true; g_partDone[s]=false;
           g_extreme[s]=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK); }
}

void ManagePos(int s)
{
   ulong magic=MagicBase+s, tk;
   if(!SelPos(magic,tk)) return;
   long type=PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL);
   double vol =PositionGetDouble(POSITION_VOLUME);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);

   if(type==POSITION_TYPE_BUY){
      if(bid>g_extreme[s]) g_extreme[s]=bid;
      // scale-out partial (only if enabled)
      if(UseScaleOut && !g_partDone[s] && bid-entry>=PartR[s]*Stop[s]){
         double cv=MathFloor((vol*PartFrac[s])/step)*step;
         if(cv>=mn && (vol-cv)>=mn){ trade.SetExpertMagicNumber(magic); trade.PositionClosePartial(tk,cv); }
         g_partDone[s]=true;
      }
      double newSL=curSL;
      if(TrailR[s]>0) newSL=MathMax(newSL,g_extreme[s]-TrailR[s]*Stop[s]);
      if(g_partDone[s]) newSL=MathMax(newSL,entry);
      if(newSL>curSL+_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),0.0); }
   } else if(type==POSITION_TYPE_SELL){
      if(ask<g_extreme[s]||g_extreme[s]==0) g_extreme[s]=ask;
      if(UseScaleOut && !g_partDone[s] && entry-ask>=PartR[s]*Stop[s]){
         double cv=MathFloor((vol*PartFrac[s])/step)*step;
         if(cv>=mn && (vol-cv)>=mn){ trade.SetExpertMagicNumber(magic); trade.PositionClosePartial(tk,cv); }
         g_partDone[s]=true;
      }
      double newSL=curSL;
      if(TrailR[s]>0){ double t=g_extreme[s]+TrailR[s]*Stop[s]; newSL=(curSL==0)?t:MathMin(newSL,t); }
      if(g_partDone[s]) newSL=(curSL==0)?entry:MathMin(newSL,entry);
      if(curSL==0 || newSL<curSL-_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),0.0); }
   }
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);

   // new day reset
   datetime ds=DayStart(now);
   if(ds!=g_day){ g_day=ds; g_orReady=false; g_vc=0; g_cumPV=0; g_cumV=0;
      for(int s=0;s<3;s++){ g_traded[s]=false; g_partDone[s]=false; g_extreme[s]=0; } }

   // ---- new closed M1 bar: update VWAP buffers, evaluate B/C signals ----
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   bool newBar=(bt!=g_lastBar);
   if(newBar){
      g_lastBar=bt;
      if(bt>=TodayOpen(now) && g_vc<MAXB){
         double bh=iHigh(_Symbol,PERIOD_M1,1), bl=iLow(_Symbol,PERIOD_M1,1), bc=iClose(_Symbol,PERIOD_M1,1);
         double bv=(double)iVolume(_Symbol,PERIOD_M1,1);
         double tp=(bh+bl+bc)/3.0;
         g_cumPV+=tp*bv; g_cumV+=bv;
         double vw=(g_cumV>0)?g_cumPV/g_cumV:bc;
         MqlDateTime bs; TimeToStruct(bt,bs);
         int j=g_vc;
         g_vwap[j]=vw; g_close[j]=bc; g_low[j]=bl; g_high[j]=bh; g_dev[j]=bc-vw; g_tod[j]=bs.hour*60+bs.min;
         g_vc++;
      }
   }

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=(ask-bid);

   // ---- EOD flatten ----
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){
      for(int s=0;s<3;s++){ ulong tk; if(SelPos(MagicBase+s,tk)){ trade.SetExpertMagicNumber(MagicBase+s); trade.PositionClose(tk); } }
      return;
   }

   // manage open positions
   for(int s=0;s<3;s++) ManagePos(s);

   bool canEnter = !(NoFridayEntry && st.day_of_week==5) && spread<=MaxSpreadPts;

   // ---- Setup A: ORB ----
   if(UseA_ORB && canEnter && !g_traded[0]){
      if(!g_orReady) ComputeORB(now);
      if(g_orReady){
         ulong tk; if(!SelPos(MagicBase+0,tk)){
            long lastVol=0; long vb[]; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vb)==1) lastVol=vb[0];
            bool volok=((double)lastVol>g_rVolAvg);
            if(volok && ask>=g_rHigh)      OpenTrade(0,+1,ask);
            else if(volok && bid<=g_rLow)  OpenTrade(0,-1,bid);
         }
      }
   }

   // ---- Setup B & C evaluate on the latest closed bar ----
   if(newBar && g_vc>0){
      int j=g_vc-1;
      int tod=g_tod[j];
      // B: VWAP trend pullback
      if(UseB_Pullback && canEnter && !g_traded[1] && g_vc>20 && tod<=EntryByHour*60){
         double vw=g_vwap[j];
         bool up = g_close[j]>vw && vw>g_vwap[j-20];
         bool dn = g_close[j]<vw && vw<g_vwap[j-20];
         if(up && g_low[j]<=vw+8.0 && g_close[j]>vw)      OpenTrade(1,+1,ask);
         else if(dn && g_high[j]>=vw-8.0 && g_close[j]<vw) OpenTrade(1,-1,bid);
      }
      // C: selective range fade (flat VWAP only)
      if(UseC_Fade && canEnter && !g_traded[2] && g_vc>40 && tod<=EntryByHour*60){
         double slope=MathAbs(g_vwap[j]-g_vwap[j-40]);
         if(slope<FadeFlatPts){
            double sig=StdDevDev(j,30);
            if(sig>0){
               double z=g_dev[j]/sig;
               if(z>=FadeZ)       OpenTrade(2,-1,bid);
               else if(z<=-FadeZ) OpenTrade(2,+1,ask);
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
