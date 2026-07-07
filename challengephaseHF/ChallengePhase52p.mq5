//+------------------------------------------------------------------+
//|                                          ChallengePhase52p.mq5    |
//|   FTMO $15k 1-STEP CHALLENGE — the best 20-day pass combo found   |
//|   (~52% monthly pass all-data, ~44% out-of-sample, median 9 days).|
//|                                                                   |
//|   High-RR / low-frequency / uncorrelated structure. Four legs:    |
//|     A_USORB : US open 16:00 server, 15-min range, 50pt stop, 4R,  |
//|               volume-confirmed, no breakeven.                     |
//|     B_EUORB : EU open 11:00 server, 30-min range, 50pt stop, 4R,  |
//|               volume-confirmed, stop -> breakeven after +1R.      |
//|     C_VWPULL: buy dips to the US-session VWAP in an uptrend        |
//|               (mirror short), 40pt stop, hard 6R TP.              |
//|     D_PDHL  : break of PRIOR DAY high/low in the US session,      |
//|               60pt stop, 3R trailing stop (no hard TP).           |
//|                                                                   |
//|   -2R daily circuit breaker halts NEW entries once the day is     |
//|   down 2R (=2*risk%) but lets open winners run. Flat 22:55 server |
//|   so nothing carries overnight/weekend. 1.0% risk per trade.      |
//|   REQUIRES A HEDGING ACCOUNT. Server time EET/EEST (FTMO).        |
//|   Backtest in the Strategy Tester before going live.             |
//+------------------------------------------------------------------+
#property copyright "FTMO research — ChallengePhase52p"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input group "=== Risk ==="
input double RiskPercent      = 1.0;    // % balance risked per trade
input double DailyBreakerR    = 2.0;    // halt NEW entries once day down this many R (0=off)
input double MaxSpreadPts     = 12.0;   // skip entry if spread wider (index points)

input group "=== A: US-open ORB (server time) ==="
input bool   UseA             = true;
input int    A_Hour           = 16;
input int    A_Min            = 0;
input int    A_ORMinutes      = 15;
input double A_StopPoints     = 50.0;
input double A_TP_R           = 4.0;
input double A_BE_R           = 0.0;     // no breakeven for A
input bool   A_VolFilter      = true;

input group "=== B: EU-open ORB (server time) ==="
input bool   UseB             = true;
input int    B_Hour           = 11;
input int    B_Min            = 0;
input int    B_ORMinutes      = 30;
input double B_StopPoints     = 50.0;
input double B_TP_R           = 4.0;
input double B_BE_R           = 1.0;     // stop -> breakeven after +1R
input bool   B_VolFilter      = true;

input group "=== C: VWAP trend pullback (US session) ==="
input bool   UseC             = true;
input int    C_SessHour       = 16;      // VWAP session start (US open)
input int    C_SessMin        = 0;
input double C_StopPoints      = 40.0;
input double C_TP_R           = 6.0;     // hard TP
input double C_Buf            = 8.0;
input int    C_TrendBars      = 20;
input int    C_EntryByHour    = 21;

input group "=== D: Prior-day high/low break (US session) ==="
input bool   UseD             = true;
input int    D_SessHour       = 16;      // start looking for the break at the US open
input double D_StopPoints     = 60.0;
input double D_TrailR         = 3.0;     // trailing stop (no hard TP)
input double D_Buf            = 2.0;     // break by this many points beyond PDH/PDL
input int    D_EntryByHour    = 22;

input group "=== Session / safety ==="
input int    EODHour          = 22;      // flatten everything after EODHour:EODMin
input int    EODMin           = 55;
input bool   NoFridayEntry    = false;
input double MaxDailyLossPct  = 2.8;     // catastrophe flatten+halt if down this % (0=off; <3% cap)
input double HaltBelowEquity  = 0.0;     // flatten+halt while equity <= this $ (0=off)

input group "=== Misc ==="
input ulong  MagicBase        = 8840000;

CTrade trade;

// per-setup config. 0=A_USORB, 1=B_EUORB, 2=C_VWPULL, 3=D_PDHL
double Stop[4], TP_R[4], BE_R[4], TrailR[4];
string Tag[4] = {"A_USORB", "B_EUORB", "C_VWPULL", "D_PDHL"};
bool   g_traded[4];
double g_extreme[4];

// ORB state: index 0 = A(US), 1 = B(EU)
double g_rHigh[2], g_rLow[2], g_rVolAvg[2];
bool   g_orReady[2];

// PDH/PDL (setup D)
double g_pdh, g_pdl;
bool   g_pdReady;

// US-session VWAP buffers (setup C)
#define MAXB 800
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB];
int    g_tod[MAXB]; int g_vc; double g_cumPV, g_cumV;

datetime g_day = 0, g_lastBar = 0;
double   g_dayStartEquity = 0.0, g_dayStartBalance = 0.0;
bool     g_halted = false, g_noNew = false;

//+------------------------------------------------------------------+
int OnInit()
{
   Stop[0]=A_StopPoints; Stop[1]=B_StopPoints; Stop[2]=C_StopPoints; Stop[3]=D_StopPoints;
   TP_R[0]=A_TP_R;       TP_R[1]=B_TP_R;       TP_R[2]=C_TP_R;       TP_R[3]=0.0;
   BE_R[0]=A_BE_R;       BE_R[1]=B_BE_R;       BE_R[2]=0.0;          BE_R[3]=0.0;
   TrailR[0]=0.0;        TrailR[1]=0.0;        TrailR[2]=0.0;        TrailR[3]=D_TrailR;
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("ChallengePhase52p v1.0: risk=%.2f%% breaker=-%.1fR  A=%d B=%d C=%d D=%d  EOD=%02d:%02d",
               RiskPercent, DailyBreakerR, UseA, UseB, UseC, UseD, EODHour, EODMin);
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
void CloseSetup(int s){ ulong tk; if(SelPos(MagicBase+s,tk)){ trade.SetExpertMagicNumber(MagicBase+s); trade.PositionClose(tk);} }

void ComputeORB(int s, datetime now, int hh, int mm, int orMin)   // s = 0(A) or 1(B)
{
   datetime t0=SessOpen(now,hh,mm), t1=t0+orMin*60;
   if(now<t1) return;
   MqlRates r[]; int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(orMin*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX, vs=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vs+=(double)r[j].tick_volume; }
   if(hi<=lo) return;
   g_rHigh[s]=hi; g_rLow[s]=lo; g_rVolAvg[s]=vs/n; g_orReady[s]=true;
}
bool VolOK(int s){ long vb[]; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vb)!=1) return false; return ((double)vb[0]>g_rVolAvg[s]); }

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

// breakeven (BE_R>0) and/or trailing (TrailR>0), preserving the TP
void ManagePos(int s)
{
   if(BE_R[s]<=0 && TrailR[s]<=0) return;
   ulong magic=MagicBase+s, tk; if(!SelPos(magic,tk)) return;
   long type=PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL), curTP=PositionGetDouble(POSITION_TP);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(type==POSITION_TYPE_BUY){
      if(bid>g_extreme[s]) g_extreme[s]=bid;
      double newSL=curSL;
      if(TrailR[s]>0)                                    newSL=MathMax(newSL, g_extreme[s]-TrailR[s]*Stop[s]);
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

void TryORB(int s, datetime now, bool useVol, int hh, int mm, int orMin)
{
   if(g_traded[s]) return;
   if(!g_orReady[s]) ComputeORB(s,now,hh,mm,orMin);
   if(!g_orReady[s]) return;
   ulong tk; if(SelPos(MagicBase+s,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(useVol && (ask>=g_rHigh[s]||bid<=g_rLow[s]) && !VolOK(s)) return;
   if(ask>=g_rHigh[s])     OpenTrade(s,+1,ask);
   else if(bid<=g_rLow[s]) OpenTrade(s,-1,bid);
}

void TryPDHL(datetime now, MqlDateTime &st)
{
   if(g_traded[3]) return;
   if(!g_pdReady){                                   // prior full-day high/low from D1
      double ph=iHigh(_Symbol,PERIOD_D1,1), pl=iLow(_Symbol,PERIOD_D1,1);
      if(ph>0 && pl>0 && ph>pl){ g_pdh=ph; g_pdl=pl; g_pdReady=true; }
   }
   if(!g_pdReady) return;
   if(st.hour<D_SessHour || st.hour>D_EntryByHour) return;
   ulong tk; if(SelPos(MagicBase+3,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(ask>=g_pdh+D_Buf)     OpenTrade(3,+1,ask);
   else if(bid<=g_pdl-D_Buf)OpenTrade(3,-1,bid);
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);

   datetime ds=DayStart(now);
   if(ds!=g_day){
      g_day=ds; g_vc=0; g_cumPV=0; g_cumV=0; g_halted=false; g_noNew=false;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
      g_dayStartBalance=AccountInfoDouble(ACCOUNT_BALANCE);
      for(int s=0;s<4;s++){ g_traded[s]=false; g_extreme[s]=0; }
      g_orReady[0]=false; g_orReady[1]=false; g_pdReady=false;
   }

   double eq=AccountInfoDouble(ACCOUNT_EQUITY), bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=(ask-bid);

   // -2R daily breaker: realized day P&L in R-units
   if(DailyBreakerR>0 && g_dayStartBalance>0){
      double rUnit=g_dayStartBalance*RiskPercent/100.0;
      if(rUnit>0 && (bal-g_dayStartBalance)<=-DailyBreakerR*rUnit) g_noNew=true;
   }
   // catastrophe guard (flatten + halt)
   bool dailyBreach=(MaxDailyLossPct>0 && g_dayStartEquity>0 &&
                     (eq-g_dayStartEquity)/g_dayStartEquity*100.0<=-MaxDailyLossPct);
   bool overallBreach=(HaltBelowEquity>0 && eq<=HaltBelowEquity);
   if(dailyBreach) g_halted=true;
   if(g_halted||overallBreach){ for(int s=0;s<4;s++) CloseSetup(s); return; }
   // EOD flatten (also flattens Friday -> no weekend carry)
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){ for(int s=0;s<4;s++) CloseSetup(s); return; }

   for(int s=0;s<4;s++) ManagePos(s);      // BE (B) + trailing (D)

   // build US-session VWAP buffers on each new closed M1 bar
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   bool newBar=(bt!=g_lastBar);
   if(newBar){
      g_lastBar=bt;
      if(bt>=SessOpen(now,C_SessHour,C_SessMin) && g_vc<MAXB){
         double bh=iHigh(_Symbol,PERIOD_M1,1), bl=iLow(_Symbol,PERIOD_M1,1), bc=iClose(_Symbol,PERIOD_M1,1);
         double bv=(double)iVolume(_Symbol,PERIOD_M1,1); double tpx=(bh+bl+bc)/3.0;
         g_cumPV+=tpx*bv; g_cumV+=bv; double vw=(g_cumV>0)?g_cumPV/g_cumV:bc;
         MqlDateTime bs; TimeToStruct(bt,bs); int j=g_vc;
         g_vwap[j]=vw; g_close[j]=bc; g_low[j]=bl; g_high[j]=bh; g_tod[j]=bs.hour*60+bs.min; g_vc++;
      }
   }

   bool canEnter=!g_noNew && !(NoFridayEntry && st.day_of_week==5) && (spread<=MaxSpreadPts);
   if(!canEnter) return;

   if(UseA) TryORB(0, now, A_VolFilter, A_Hour, A_Min, A_ORMinutes);
   if(UseB) TryORB(1, now, B_VolFilter, B_Hour, B_Min, B_ORMinutes);
   if(UseD) TryPDHL(now, st);

   // C: VWAP pullback on each new closed bar
   if(UseC && newBar && !g_traded[2] && g_vc>C_TrendBars){
      int j=g_vc-1;
      if(g_tod[j] <= C_EntryByHour*60){
         double vw=g_vwap[j];
         bool up=(g_close[j]>vw && vw>g_vwap[j-C_TrendBars]);
         bool dn=(g_close[j]<vw && vw<g_vwap[j-C_TrendBars]);
         if(up && g_low[j]<=vw+C_Buf && g_close[j]>vw)        OpenTrade(2,+1,ask);
         else if(dn && g_high[j]>=vw-C_Buf && g_close[j]<vw)  OpenTrade(2,-1,bid);
      }
   }
}
//+------------------------------------------------------------------+
