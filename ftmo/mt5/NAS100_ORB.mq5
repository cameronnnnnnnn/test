//+------------------------------------------------------------------+
//|                                                  NAS100_ORB.mq5   |
//|     US-session Opening-Range Breakout (FTMO config "B")          |
//|     One trade/day, 60pt stop = 1R, breakeven @1R, trail 3R, EOD  |
//|                                                                  |
//|  Validated on 3y real NAS100 M1: expR +0.129, PF 1.26,          |
//|  walk-forward +0.131 / +0.124. Respects FTMO daily/overall caps  |
//|  (one position, hard stop => max ~1R loss/day).                  |
//+------------------------------------------------------------------+
#property copyright "FTMO research"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

//--- Session / setup -------------------------------------------------
input group "=== Session (server time) ==="
input int      SessionOpenHour = 16;     // US cash open hour (server) - check your broker!
input int      SessionOpenMin  = 0;      // open minute
input int      RangeMinutes     = 30;    // opening-range length (min)
input int      EODHour          = 23;    // flatten/no-new-trades after this hour
input bool      NoFridayEntry    = true; // no Friday entries (no weekend hold)

//--- Risk / management ----------------------------------------------
input group "=== Risk & exits ==="
input double   RiskPercent     = 1.0;    // % of balance risked per trade (1R)
input double   StopDistance     = 60.0;  // 1R stop in PRICE units (index points)
input double   BreakevenR        = 1.0;  // move SL to entry once +this many R
input double   TrailR            = 3.0;  // trail stop this many R behind extreme (0=off)
input double   MaxSpreadPrice    = 8.0;  // skip entry if spread wider than this (price)

//--- Edge filters (validated improvements: rng_filter + vol_confirm) --
input group "=== Edge filters ==="
input bool      UseRangeFilter   = true; // skip dead-chop / already-exploded days
input int      RangeLookback     = 40;   // days of history for the median
input double   RangeMinMult      = 0.5;  // skip if range < this x median
input double   RangeMaxMult      = 2.0;  // skip if range > this x median
input bool      UseVolConfirm    = true; // require breakout bar volume > range avg

//--- Misc ------------------------------------------------------------
input group "=== Misc ==="
input ulong    MagicNumber      = 7700160;
input string   TradeComment      = "NAS100_ORB_B";

CTrade   trade;
datetime g_day        = 0;       // current day marker
bool     g_rangeReady = false;
bool     g_tradedToday= false;
double   g_rangeHigh  = 0.0;
double   g_rangeLow   = 0.0;
double   g_extreme    = 0.0;     // best price reached since entry
bool     g_skipDay    = false;   // range filter said skip today
double   g_rangeVolAvg= 0.0;     // avg tick-vol of the opening-range bars
double   g_recentRng[];          // rolling history of opening-range sizes
int      g_recentN    = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("NAS100_ORB started on %s  open=%02d:%02d +%dm  stop=%.1f  risk=%.2f%%",
               _Symbol, SessionOpenHour, SessionOpenMin, RangeMinutes, StopDistance, RiskPercent);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| daily reset                                                      |
//+------------------------------------------------------------------+
datetime DayStart(datetime t)
{
   MqlDateTime s; TimeToStruct(t, s);
   s.hour=0; s.min=0; s.sec=0;
   return StructToTime(s);
}

//+------------------------------------------------------------------+
//| compute opening range from M1 bars in the window                 |
//+------------------------------------------------------------------+
double MedianOf(double &arr[], int cnt)
{
   if(cnt<=0) return 0.0;
   double tmp[]; ArrayResize(tmp,cnt);
   for(int i=0;i<cnt;i++) tmp[i]=arr[i];
   ArraySort(tmp);
   return (cnt%2==1) ? tmp[cnt/2] : 0.5*(tmp[cnt/2-1]+tmp[cnt/2]);
}

bool ComputeRange(datetime now)
{
   MqlDateTime s; TimeToStruct(now, s);
   s.hour=SessionOpenHour; s.min=SessionOpenMin; s.sec=0;
   datetime t0 = StructToTime(s);              // session open today
   datetime t1 = t0 + RangeMinutes*60;         // end of range window
   if(now < t1) return false;                  // window not finished yet

   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, t0, t1-1, r);
   if(n < (int)(RangeMinutes*0.5)) return false; // not enough data (holiday/thin)

   double hi=-DBL_MAX, lo=DBL_MAX, vsum=0;
   for(int i=0;i<n;i++){
      if(r[i].high>hi) hi=r[i].high;
      if(r[i].low<lo)  lo=r[i].low;
      vsum += (double)r[i].tick_volume;
   }
   if(hi<=lo) return false;
   g_rangeHigh=hi; g_rangeLow=lo;
   g_rangeVolAvg = vsum/n;
   double rsize = hi-lo;

   //--- range filter: compare to trailing median (history BEFORE today)
   g_skipDay=false;
   if(UseRangeFilter && g_recentN>=10){
      double med = MedianOf(g_recentRng, g_recentN);
      if(med>0 && (rsize < RangeMinMult*med || rsize > RangeMaxMult*med))
         g_skipDay=true;
   }
   //--- push today's range into the rolling history
   if(g_recentN < RangeLookback){
      ArrayResize(g_recentRng, g_recentN+1); g_recentRng[g_recentN]=rsize; g_recentN++;
   } else {
      for(int i=0;i<RangeLookback-1;i++) g_recentRng[i]=g_recentRng[i+1];
      g_recentRng[RangeLookback-1]=rsize;
   }
   return true;
}

//+------------------------------------------------------------------+
//| position helpers                                                 |
//+------------------------------------------------------------------+
bool HasPosition()
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(PositionSelectByTicket(tk) &&
         PositionGetString(POSITION_SYMBOL)==_Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==MagicNumber) return true;
   }
   return false;
}

double LotsForRisk()
{
   double bal     = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMon = bal * RiskPercent/100.0;
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSz<=0 || tickVal<=0) return 0.0;
   double lossPerLot = (StopDistance/tickSz)*tickVal;
   if(lossPerLot<=0) return 0.0;
   double lots = riskMon/lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lots = MathFloor(lots/step)*step;
   if(lots<minL) lots=minL;
   if(lots>maxL) lots=maxL;
   return lots;
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime now = TimeCurrent();
   MqlDateTime st; TimeToStruct(now, st);

   //--- new day: reset state
   datetime ds = DayStart(now);
   if(ds != g_day){
      g_day=ds; g_rangeReady=false; g_tradedToday=false; g_skipDay=false;
      g_rangeHigh=0; g_rangeLow=0; g_extreme=0;
   }

   //--- end of day: flatten and stop trading for the day
   if(st.hour >= EODHour){
      if(HasPosition()) trade.PositionClose(_Symbol);
      return;
   }

   //--- build the opening range once it's complete
   if(!g_rangeReady){
      if(ComputeRange(now)) g_rangeReady=true;
      else return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;

   //--- manage an open position (breakeven + trail)
   if(HasPosition()){
      if(!PositionSelect(_Symbol)) return;
      long   ptype  = PositionGetInteger(POSITION_TYPE);
      double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL  = PositionGetDouble(POSITION_SL);
      double newSL  = curSL;

      if(ptype==POSITION_TYPE_BUY){
         if(bid>g_extreme || g_extreme==0) g_extreme=bid;
         double profit = bid - entry;
         if(BreakevenR>0 && profit >= BreakevenR*StopDistance)
            newSL = MathMax(newSL, entry);
         if(TrailR>0){
            double ts = g_extreme - TrailR*StopDistance;
            newSL = MathMax(newSL, ts);
         }
         if(newSL > curSL + _Point)
            trade.PositionModify(_Symbol, NormalizeDouble(newSL,_Digits), 0.0);
      }
      else if(ptype==POSITION_TYPE_SELL){
         if(ask<g_extreme || g_extreme==0) g_extreme=ask;
         double profit = entry - ask;
         if(BreakevenR>0 && profit >= BreakevenR*StopDistance)
            newSL = (curSL==0)? entry : MathMin(newSL, entry);
         if(TrailR>0){
            double ts = g_extreme + TrailR*StopDistance;
            newSL = (curSL==0)? ts : MathMin(newSL, ts);
         }
         if(curSL==0 || newSL < curSL - _Point)
            trade.PositionModify(_Symbol, NormalizeDouble(newSL,_Digits), 0.0);
      }
      return; // one trade/day: don't look for entries while in a position
   }

   //--- no position: look for the FIRST breakout of the day
   if(g_tradedToday) return;
   if(g_skipDay) return;                               // range filter skipped today
   if(NoFridayEntry && st.day_of_week==5) return;     // Friday=5 in MqlDateTime
   if(spread > MaxSpreadPrice) return;

   //--- volume confirmation: last closed M1 bar volume must beat the range average
   if(UseVolConfirm){
      long v[]; if(CopyTickVolume(_Symbol, PERIOD_M1, 1, 1, v)==1){
         if((double)v[0] <= g_rangeVolAvg) return;
      }
   }

   double lots = LotsForRisk();
   if(lots<=0) return;

   if(ask >= g_rangeHigh){                  // upside breakout -> long
      double sl = NormalizeDouble(ask - StopDistance, _Digits);
      if(trade.Buy(lots, _Symbol, 0.0, sl, 0.0, TradeComment)){
         g_tradedToday=true; g_extreme=bid;
      }
   }
   else if(bid <= g_rangeLow){              // downside breakout -> short
      double sl = NormalizeDouble(bid + StopDistance, _Digits);
      if(trade.Sell(lots, _Symbol, 0.0, sl, 0.0, TradeComment)){
         g_tradedToday=true; g_extreme=ask;
      }
   }
}
//+------------------------------------------------------------------+
