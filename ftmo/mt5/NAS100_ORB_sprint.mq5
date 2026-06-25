//+------------------------------------------------------------------+
//|                                            NAS100_ORB_sprint.mq5  |
//|   1-MONTH SPRINT preset — multi-session US Opening-Range Breakout |
//|   Trades 15h AND 16h (server) opens in ONE EA, 80pt stop=1R,      |
//|   BE@1R, HARD TP@3R, EOD flat, range+volume filters, NO overnight.|
//|                                                                   |
//|   FTMO 1-Step 50% BEST-DAY rule (best day <= 50% of POSITIVE-day  |
//|   sum, dilutable, NOT a breach). It's mild, so the TP barely       |
//|   matters; 3R is the optimum: pass<=1mo ~46% long-only / ~37% both|
//|   eventual ~56%/48%. See ftmo/mc_bestday_rule.py.                 |
//|   REQUIRES A HEDGING ACCOUNT (two positions can be open at once). |
//|   Backtest in the Strategy Tester before going live.              |
//+------------------------------------------------------------------+
#property copyright "FTMO research"
#property version   "1.41"
#property strict
#include <Trade/Trade.mqh>

input group "=== Sessions (server time) ==="
input string   SessionHours    = "15,16"; // comma-separated server open hours
input int      RangeMinutes     = 30;     // opening-range length (min)
input int      EODHour          = 23;     // flatten/no-new-trades after this hour
input bool      NoFridayEntry    = true;  // no Friday entries
input bool      AllowOpposing    = false; // false = block a new trade opposite to an in-PROFIT position
input bool      LongOnly         = false; // true = take ONLY long breakouts (leans on NAS up-drift; ~+12pp 1-mo pass in backtest, but a directional bet)

input group "=== Risk & exits (sprint preset) ==="
input double   RiskPercent     = 1.25;   // % risked per trade (1R)
input double   StopDistance     = 80.0;  // 1R stop in PRICE units (index points)
input double   BreakevenR        = 1.0;  // move SL to entry once +this many R
input double   TrailR            = 5.0;  // trail stop this many R behind extreme (dominated when TakeProfitR>0)
input double   TakeProfitR        = 3.0;  // hard TP this many R (0 = trail-only). 3R is the optimum under FTMO's real 50% best-day rule (best day <= 50% of positive-day sum, dilutable). Trail-only/4R are within ~1pp; <=2R needlessly sacrifices edge. See mc_bestday_rule.py.
input double   DailyProfitCap     = 0.0;  // optional: stop opening NEW entries once realized profit today >= this $ (0=off). NOT needed for the best-day rule (no hard daily cap); leave off unless you want a manual daily lock.
input double   MaxSpreadPrice    = 12.0; // skip entry if spread wider than this

input group "=== Edge filters ==="
input bool      UseRangeFilter   = true; // skip dead-chop / already-exploded days
input int      RangeLookback     = 40;   // days of history for the median (<=80)
input double   RangeMinMult      = 0.5;
input double   RangeMaxMult      = 2.0;
input bool      UseVolConfirm    = true; // breakout bar volume > range avg

input group "=== Misc ==="
input ulong    MagicBase        = 7700000; // each session uses MagicBase + hour

CTrade   trade;
#define MAXS 8
int      g_nSess=0;
int      g_hours[MAXS];
double   g_rHigh[MAXS], g_rLow[MAXS], g_rVolAvg[MAXS], g_extreme[MAXS];
bool     g_ready[MAXS], g_traded[MAXS], g_skip[MAXS];
double   g_hist[MAXS][80];
int      g_histN[MAXS];
datetime g_day=0;
double   g_dayStartBal=0;

//+------------------------------------------------------------------+
int OnInit()
{
   string parts[];
   int k=StringSplit(SessionHours, ',', parts);
   g_nSess=0;
   for(int i=0;i<k && g_nSess<MAXS;i++){
      string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ g_hours[g_nSess]=(int)StringToInteger(s); g_histN[g_nSess]=0; g_nSess++; }
   }
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("NAS100_ORB_sprint: %d sessions, stop=%.0f risk=%.2f%%", g_nSess, StopDistance, RiskPercent);
   return(INIT_SUCCEEDED);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

double MedianRow(int row, int cnt)
{
   if(cnt<=0) return 0.0;
   double tmp[]; ArrayResize(tmp,cnt);
   for(int i=0;i<cnt;i++) tmp[i]=g_hist[row][i];
   ArraySort(tmp);
   return (cnt%2==1)? tmp[cnt/2] : 0.5*(tmp[cnt/2-1]+tmp[cnt/2]);
}

bool ComputeRange(int i, datetime now)
{
   MqlDateTime s; TimeToStruct(now,s); s.hour=g_hours[i]; s.min=0; s.sec=0;
   datetime t0=StructToTime(s), t1=t0+RangeMinutes*60;
   if(now<t1) return false;
   MqlRates r[];
   int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(RangeMinutes*0.5)) return false;
   double hi=-DBL_MAX, lo=DBL_MAX, vsum=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vsum+=(double)r[j].tick_volume; }
   if(hi<=lo) return false;
   g_rHigh[i]=hi; g_rLow[i]=lo; g_rVolAvg[i]=vsum/n;
   double rsize=hi-lo;
   g_skip[i]=false;
   if(UseRangeFilter && g_histN[i]>=10){
      double med=MedianRow(i,g_histN[i]);
      if(med>0 && (rsize<RangeMinMult*med || rsize>RangeMaxMult*med)) g_skip[i]=true;
   }
   int cap=MathMin(RangeLookback,80);
   if(g_histN[i]<cap){ g_hist[i][g_histN[i]]=rsize; g_histN[i]++; }
   else { for(int j=0;j<cap-1;j++) g_hist[i][j]=g_hist[i][j+1]; g_hist[i][cap-1]=rsize; }
   return true;
}

// is there an open position (from this EA) opposite to wantDir that is IN PROFIT?
bool OpposingInProfit(int wantDir)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      ulong mg=(ulong)PositionGetInteger(POSITION_MAGIC);
      bool ours=false;
      for(int s=0;s<g_nSess;s++) if(mg==MagicBase+g_hours[s]) ours=true;
      if(!ours) continue;
      long   tp   = PositionGetInteger(POSITION_TYPE);
      double prof = PositionGetDouble(POSITION_PROFIT);   // floating P/L in account ccy
      if(prof<=0) continue;                                // only block against winners
      if(wantDir>0 && tp==POSITION_TYPE_SELL) return true; // want long, a profitable short is open
      if(wantDir<0 && tp==POSITION_TYPE_BUY)  return true; // want short, a profitable long is open
   }
   return false;
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

double LotsForRisk()
{
   double riskMon=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0) return 0.0;
   double lpl=(StopDistance/ts)*tv; if(lpl<=0) return 0.0;
   double lots=riskMon/lpl;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN), mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   lots=MathFloor(lots/step)*step; if(lots<mn)lots=mn; if(lots>mx)lots=mx;
   return lots;
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);
   datetime ds=DayStart(now);
   if(ds!=g_day){ g_day=ds; g_dayStartBal=AccountInfoDouble(ACCOUNT_BALANCE); for(int i=0;i<g_nSess;i++){ g_ready[i]=false; g_traded[i]=false; g_skip[i]=false; g_extreme[i]=0; } }

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=ask-bid;

   // end of day: flatten every session's position
   if(st.hour>=EODHour){
      for(int i=0;i<g_nSess;i++){ ulong tk; if(SelPos(MagicBase+g_hours[i],tk)){ trade.SetExpertMagicNumber(MagicBase+g_hours[i]); trade.PositionClose(tk); } }
      return;
   }

   // volume of last closed M1 bar (for confirm)
   long vbuf[]; long lastVol=0; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vbuf)==1) lastVol=vbuf[0];

   for(int i=0;i<g_nSess;i++){
      ulong magic=MagicBase+g_hours[i];
      // build range
      if(!g_ready[i]){ if(ComputeRange(i,now)) g_ready[i]=true; else continue; }

      // manage this session's open position
      ulong tk;
      if(SelPos(magic,tk)){
         long type=PositionGetInteger(POSITION_TYPE);
         double entry=PositionGetDouble(POSITION_PRICE_OPEN), curSL=PositionGetDouble(POSITION_SL), curTP=PositionGetDouble(POSITION_TP), newSL;
         if(type==POSITION_TYPE_BUY){
            if(bid>g_extreme[i]||g_extreme[i]==0) g_extreme[i]=bid;
            newSL=curSL;
            if(BreakevenR>0 && bid-entry>=BreakevenR*StopDistance) newSL=MathMax(newSL,entry);
            if(TrailR>0) newSL=MathMax(newSL,g_extreme[i]-TrailR*StopDistance);
            if(newSL>curSL+_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),curTP); }
         } else if(type==POSITION_TYPE_SELL){
            if(ask<g_extreme[i]||g_extreme[i]==0) g_extreme[i]=ask;
            newSL=curSL;
            if(BreakevenR>0 && entry-ask>=BreakevenR*StopDistance) newSL=(curSL==0)?entry:MathMin(newSL,entry);
            if(TrailR>0){ double ts=g_extreme[i]+TrailR*StopDistance; newSL=(curSL==0)?ts:MathMin(newSL,ts); }
            if(curSL==0 || newSL<curSL-_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),curTP); }
         }
         continue; // one position per session
      }

      // entry
      if(g_traded[i] || g_skip[i]) continue;
      if(DailyProfitCap>0 && AccountInfoDouble(ACCOUNT_BALANCE)-g_dayStartBal>=DailyProfitCap) continue; // daily consistency backstop
      if(NoFridayEntry && st.day_of_week==5) continue;
      if(spread>MaxSpreadPrice) continue;
      if(UseVolConfirm && (double)lastVol<=g_rVolAvg[i]) continue;
      double lots=LotsForRisk(); if(lots<=0) continue;
      trade.SetExpertMagicNumber(magic);
      if(ask>=g_rHigh[i] && (AllowOpposing || !OpposingInProfit(+1))){
         double sl=NormalizeDouble(ask-StopDistance,_Digits);
         double tp=(TakeProfitR>0)?NormalizeDouble(ask+TakeProfitR*StopDistance,_Digits):0.0;
         if(trade.Buy(lots,_Symbol,0.0,sl,tp,"ORB"+IntegerToString(g_hours[i]))){ g_traded[i]=true; g_extreme[i]=bid; }
      } else if(!LongOnly && bid<=g_rLow[i] && (AllowOpposing || !OpposingInProfit(-1))){
         double sl=NormalizeDouble(bid+StopDistance,_Digits);
         double tp=(TakeProfitR>0)?NormalizeDouble(bid-TakeProfitR*StopDistance,_Digits):0.0;
         if(trade.Sell(lots,_Symbol,0.0,sl,tp,"ORB"+IntegerToString(g_hours[i]))){ g_traded[i]=true; g_extreme[i]=ask; }
      }
   }
}
//+------------------------------------------------------------------+
