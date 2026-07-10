//+------------------------------------------------------------------+
//|                                              NAS100_ORB_88.mq5    |
//|   FTMO $15k 1-Step "88% / ~2-month" config (aggressive) — SEPARATE EA.       |
//|   Does NOT replace NAS100_ORB_sprint.mq5 (different MagicBase).   |
//|                                                                   |
//|   NAS100 opening-range breakout, 15h & 16h server sessions, both  |
//|   directions, 80pt stop=1R. NEW vs the sprint EA:                 |
//|     • Causal daily-ATR-percentile VOL GATE: only trade when the   |
//|       prior day's ATR percentile >= 0.50 (skip dead-vol chop).    |
//|     • PARTIAL scale-out: close 50% at +2R, move rest to BE.       |
//|     • Runner trails 5R behind extreme; NO hard take-profit.       |
//|     • RiskPercent 1.25% (faster, higher ruin risk).                                            |
//|   Verified ~88.3% pass on FTMO's static $13,500 floor, ~11.6% blow (block-boot |
//|   MC, full rules). See FTMO_95_Strategy/README.md. REQUIRES a     |
//|   HEDGING account (two positions can be open at once).            |
//+------------------------------------------------------------------+
#property copyright "FTMO research"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input group "=== Sessions (server time) ==="
input string   SessionHours     = "15,16"; // comma-separated server open hours
input int      RangeMinutes     = 30;      // opening-range length (min)
input int      EODHour          = 23;      // flatten/no-new-trades after this hour
input bool     NoFridayEntry    = false;   // this config trades Fridays (backtest kept them)
input bool     AllowOpposing    = false;   // false = block a new trade opposite an in-PROFIT position
input bool     LongOnly         = false;   // both directions

input group "=== Volatility regime gate (causal, prior-day) ==="
input double   RegimeMin        = 0.50;    // only trade when prior-day ATR percentile >= this
input double   RegimeMax        = 1.00;    // ... and <= this
input int      AtrPeriod        = 14;      // daily ATR length
input int      RegimeLookback   = 120;     // trailing window for the percentile rank

input group "=== Risk & exits ==="
input double   RiskPercent      = 1.25;    // % risked per trade (1R) -- aggressive: faster pass, ~11.6% blow-up
input double   StopDistance     = 80.0;    // 1R stop in price units (index points)
input double   BreakevenR       = 1.0;     // move SL to entry once +this many R
input double   PartialR         = 2.0;     // scale out at +this many R
input double   PartialFraction  = 0.5;     // fraction of the position to close at PartialR
input bool     PartialToBE      = true;    // after partial, force remaining SL to breakeven
input double   TrailR           = 5.0;     // trail remaining stop this many R behind extreme
input double   TakeProfitR      = 0.0;     // 0 = no hard TP (let the runner trail)
input double   MaxSpreadPrice    = 12.0;   // skip entry if spread wider than this

input group "=== Edge filters ==="
input bool     UseRangeFilter   = true;
input int      RangeLookback     = 40;
input double   RangeMinMult      = 0.5;
input double   RangeMaxMult      = 2.0;
input bool     UseVolConfirm    = true;

input group "=== Misc ==="
input ulong    MagicBase        = 7900000; // DIFFERENT base (sprint=7700000, 95cfg=7800000)

CTrade   trade;
#define MAXS 8
int      g_nSess=0;
int      g_hours[MAXS];
double   g_rHigh[MAXS], g_rLow[MAXS], g_rVolAvg[MAXS], g_extreme[MAXS];
bool     g_ready[MAXS], g_traded[MAXS], g_skip[MAXS], g_partial[MAXS];
double   g_hist[MAXS][80];
int      g_histN[MAXS];
datetime g_day=0;
double   g_atrpct=-1.0;    // prior-day ATR percentile, recomputed each new day

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
   PrintFormat("NAS100_ORB_88: %d sessions, stop=%.0f risk=%.2f%% regime[%.2f,%.2f] partial %.0f%%@%.1fR",
               g_nSess, StopDistance, RiskPercent, RegimeMin, RegimeMax, PartialFraction*100, PartialR);
   return(INIT_SUCCEEDED);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

//+------------------------------------------------------------------+
//| Causal daily ATR percentile: percentile rank of YESTERDAY's ATR  |
//| within the trailing RegimeLookback window, using COMPLETED daily |
//| bars only (shift>=1) -> no lookahead into today's forming bar.   |
//+------------------------------------------------------------------+
double DailyAtrPctCausal()
{
   int need = RegimeLookback + AtrPeriod + 2;
   MqlRates d[]; ArraySetAsSeries(d,false);
   int n = CopyRates(_Symbol, PERIOD_D1, 1, need, d);   // start at shift 1 (last completed day)
   if(n < RegimeLookback + AtrPeriod + 1) return -1.0;
   double tr[]; ArrayResize(tr,n);
   for(int i=0;i<n;i++) tr[i]=0.0;
   for(int i=1;i<n;i++){
      double h=d[i].high, l=d[i].low, pc=d[i-1].close;
      tr[i]=MathMax(h-l, MathMax(MathAbs(h-pc), MathAbs(l-pc)));
   }
   double atr[]; ArrayResize(atr,n);
   for(int i=0;i<n;i++) atr[i]=0.0;
   for(int i=AtrPeriod;i<n;i++){
      double s=0; for(int j=i-AtrPeriod+1;j<=i;j++) s+=tr[j];
      atr[i]=s/AtrPeriod;
   }
   double cur=atr[n-1];
   int start=n-RegimeLookback; if(start<AtrPeriod) start=AtrPeriod;
   int cnt=0, tot=0;
   for(int i=start;i<n;i++){ tot++; if(atr[i]<=cur) cnt++; }
   if(tot<=0) return -1.0;
   return (double)cnt/(double)tot;
}

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
      double prof = PositionGetDouble(POSITION_PROFIT);
      if(prof<=0) continue;
      if(wantDir>0 && tp==POSITION_TYPE_SELL) return true;
      if(wantDir<0 && tp==POSITION_TYPE_BUY)  return true;
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

double NormVolDown(double v)
{
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0) step=0.01;
   double r=MathFloor(v/step)*step;
   return NormalizeDouble(r,2);
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
   return NormalizeDouble(lots,2);
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);
   datetime ds=DayStart(now);
   if(ds!=g_day){
      g_day=ds; g_atrpct=DailyAtrPctCausal();
      for(int i=0;i<g_nSess;i++){ g_ready[i]=false; g_traded[i]=false; g_skip[i]=false; g_partial[i]=false; g_extreme[i]=0; }
   }

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=ask-bid;
   double minVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);

   // end of day: flatten every session's position
   if(st.hour>=EODHour){
      for(int i=0;i<g_nSess;i++){ ulong tk; if(SelPos(MagicBase+g_hours[i],tk)){ trade.SetExpertMagicNumber(MagicBase+g_hours[i]); trade.PositionClose(tk); } }
      return;
   }

   long vbuf[]; long lastVol=0; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vbuf)==1) lastVol=vbuf[0];

   for(int i=0;i<g_nSess;i++){
      ulong magic=MagicBase+g_hours[i];
      if(!g_ready[i]){ if(ComputeRange(i,now)) g_ready[i]=true; else continue; }

      // manage this session's open position
      ulong tk;
      if(SelPos(magic,tk)){
         long type=PositionGetInteger(POSITION_TYPE);
         double entry=PositionGetDouble(POSITION_PRICE_OPEN), curSL=PositionGetDouble(POSITION_SL),
                curTP=PositionGetDouble(POSITION_TP), posVol=PositionGetDouble(POSITION_VOLUME), newSL;
         if(type==POSITION_TYPE_BUY){
            if(bid>g_extreme[i]||g_extreme[i]==0) g_extreme[i]=bid;
            // partial scale-out at +PartialR
            if(PartialR>0 && !g_partial[i] && (bid-entry)>=PartialR*StopDistance){
               double cv=NormVolDown(posVol*PartialFraction);
               if(cv>=minVol && (posVol-cv)>=minVol){
                  trade.SetExpertMagicNumber(magic);
                  if(trade.PositionClosePartial(tk,cv)) g_partial[i]=true;
               } else g_partial[i]=true; // too small to split -> don't retry
               if(PositionSelectByTicket(tk)){ posVol=PositionGetDouble(POSITION_VOLUME); curSL=PositionGetDouble(POSITION_SL); }
            }
            newSL=curSL;
            if(BreakevenR>0 && bid-entry>=BreakevenR*StopDistance) newSL=MathMax(newSL,entry);
            if(PartialToBE && g_partial[i]) newSL=MathMax(newSL,entry);
            if(TrailR>0) newSL=MathMax(newSL,g_extreme[i]-TrailR*StopDistance);
            if(newSL>curSL+_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),curTP); }
         } else if(type==POSITION_TYPE_SELL){
            if(ask<g_extreme[i]||g_extreme[i]==0) g_extreme[i]=ask;
            if(PartialR>0 && !g_partial[i] && (entry-ask)>=PartialR*StopDistance){
               double cv=NormVolDown(posVol*PartialFraction);
               if(cv>=minVol && (posVol-cv)>=minVol){
                  trade.SetExpertMagicNumber(magic);
                  if(trade.PositionClosePartial(tk,cv)) g_partial[i]=true;
               } else g_partial[i]=true;
               if(PositionSelectByTicket(tk)){ posVol=PositionGetDouble(POSITION_VOLUME); curSL=PositionGetDouble(POSITION_SL); }
            }
            newSL=curSL;
            if(BreakevenR>0 && entry-ask>=BreakevenR*StopDistance) newSL=(curSL==0)?entry:MathMin(newSL,entry);
            if(PartialToBE && g_partial[i]) newSL=(curSL==0)?entry:MathMin(newSL,entry);
            if(TrailR>0){ double ts=g_extreme[i]+TrailR*StopDistance; newSL=(curSL==0)?ts:MathMin(newSL,ts); }
            if(curSL==0 || newSL<curSL-_Point){ trade.SetExpertMagicNumber(magic); trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),curTP); }
         }
         continue; // one position per session
      }

      // entry
      if(g_traded[i] || g_skip[i]) continue;
      if(g_atrpct<RegimeMin || g_atrpct>RegimeMax) continue;      // causal volatility gate
      if(NoFridayEntry && st.day_of_week==5) continue;
      if(spread>MaxSpreadPrice) continue;
      if(UseVolConfirm && (double)lastVol<=g_rVolAvg[i]) continue;
      double lots=LotsForRisk(); if(lots<=0) continue;
      trade.SetExpertMagicNumber(magic);
      if(ask>=g_rHigh[i] && (AllowOpposing || !OpposingInProfit(+1))){
         double sl=NormalizeDouble(ask-StopDistance,_Digits);
         double tp=(TakeProfitR>0)?NormalizeDouble(ask+TakeProfitR*StopDistance,_Digits):0.0; // config default: 0 = none
         if(trade.Buy(lots,_Symbol,0.0,sl,tp,"ORB88_"+IntegerToString(g_hours[i]))){ g_traded[i]=true; g_extreme[i]=bid; }
      } else if(!LongOnly && bid<=g_rLow[i] && (AllowOpposing || !OpposingInProfit(-1))){
         double sl=NormalizeDouble(bid+StopDistance,_Digits);
         double tp=(TakeProfitR>0)?NormalizeDouble(bid-TakeProfitR*StopDistance,_Digits):0.0;
         if(trade.Sell(lots,_Symbol,0.0,sl,tp,"ORB88_"+IntegerToString(g_hours[i]))){ g_traded[i]=true; g_extreme[i]=ask; }
      }
   }
}
//+------------------------------------------------------------------+
