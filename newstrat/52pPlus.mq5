//+------------------------------------------------------------------+
//|                                                     52pPlus.mq5  |
//|  FTMO 15k 1-Step - ChallengePhase52pPlus: the grand-unification  |
//|  build. Best 20-trading-day pass found in the whole project:     |
//|    TE-20d 54.5% OOS (52p: 49.2%) | 1mo 58.0% | 2mo 74.6% | 3mo 83.1%
//|                                                                  |
//|  EIGHT legs, all OOS-validated, pairwise daily-R corr ~0:        |
//|   0 A_USORB : US open 16:00, 15-min range, 50pt stop, 4R, vol    |
//|   1 B_EUORB : EU open 11:00, 30-min range, 50pt stop, 4R, BE@1R  |
//|   2 C_VWPULL: VWAP pullback (16:00 session), 40pt stop, 6R TP    |
//|   3 D_PDHL  : prior-day H/L break, 60pt stop, 3R trail           |
//|   4 E_FADE  : VWAP fade, ONLY on prior-day RANGE-regime days     |
//|               (D1 ADX14<20 && Choppiness14>55), 0.20xATR stop,   |
//|               50% off at +1R -> BE, trail 2R. 55% WR leg.        |
//|   5 F_TOM   : turn-of-month long (last td + first 3 of month),   |
//|               16:00 entry, 60pt stop, BE@1R, 3R trail            |
//|   6 G_MON   : Monday US-session long, 16:30, 0.5xATR stop, EOD   |
//|   7 H_GER   : GER40 long 18:00->18:45 (DAX cash-close drift),    |
//|               0.25xATR(GER40) stop  [SECOND SYMBOL]              |
//|                                                                  |
//|  -2R daily breaker (halts NEW entries), 2.8% catastrophe guard,  |
//|  EOD flatten 22:55 server. Server time EET/EEST (FTMO). HEDGING  |
//|  account required. Attach to the NAS100/US100 chart; the GER40   |
//|  leg trades via the GER40Symbol input (leave UseH=false if your  |
//|  account lacks GER40). RiskPercent 0.75 = 20-day-sprint optimum; |
//|  use 0.50 for the safer ~2-month profile. Backtest before live.  |
//+------------------------------------------------------------------+
#property copyright "FTMO research - ChallengePhase52pPlus"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input group "=== Risk ==="
input double RiskPercent      = 0.75;   // % balance per trade (0.75=20d sprint, 0.50=2mo safe)
input double DailyBreakerR    = 2.0;    // halt NEW entries once day down this many R (0=off)
input double MaxSpreadPts     = 12.0;   // skip entries if spread wider (points)

input group "=== Legs ==="
input bool   UseA = true;   // A: US-open ORB
input bool   UseB = true;   // B: EU-open ORB
input bool   UseC = true;   // C: VWAP pullback
input bool   UseD = true;   // D: prior-day H/L break
input bool   UseE = true;   // E: VWAP fade on range-regime days
input bool   UseF = true;   // F: turn-of-month long
input bool   UseG = true;   // G: Monday session long
input bool   UseH = true;   // H: GER40 close drift
input string GER40Symbol     = "GER40.cash";

input group "=== A: US ORB ==="
input int    A_Hour = 16;  input int A_Min = 0;  input int A_ORMinutes = 15;
input double A_StopPoints = 50.0;  input double A_TP_R = 4.0;
input group "=== B: EU ORB ==="
input int    B_Hour = 11;  input int B_Min = 0;  input int B_ORMinutes = 30;
input double B_StopPoints = 50.0;  input double B_TP_R = 4.0;  input double B_BE_R = 1.0;
input group "=== C: VWAP pullback ==="
input double C_StopPoints = 40.0;  input double C_TP_R = 6.0;  input double C_Buf = 8.0;
input int    C_TrendBars = 20;     input int C_EntryByHour = 21;
input group "=== D: PDH/PDL ==="
input double D_StopPoints = 60.0;  input double D_TrailR = 3.0;  input double D_Buf = 2.0;
input int    D_SessHour = 16;      input int D_EntryByHour = 22;
input group "=== E: regime fade ==="
input double E_FadeZ = 2.0;        // z-score of deviation from session VWAP
input double E_StopATR = 0.20;     // stop = this x D1 ATR(14)
input double E_PartialR = 1.0;     // take 50% off here, stop -> BE
input double E_TrailR = 2.0;       // then trail the rest
input double E_FlatPts = 15.0;     // VWAP must be flat: |vwap now - vwap 40 bars ago| <= this
input int    E_EntryByHour = 21;
input group "=== F: turn-of-month ==="
input double F_StopPoints = 60.0;  input double F_TrailR = 3.0;  input double F_BE_R = 1.0;
input group "=== G: Monday ==="
input double G_StopATR = 0.50;     // stop = this x D1 ATR(14)
input group "=== H: GER40 ==="
input int    H_EntryHour = 18;  input int H_EntryMin = 0;
input int    H_ExitHour  = 18;  input int H_ExitMin  = 45;
input double H_StopATR   = 0.25;   // stop = this x GER40 D1 ATR(14)

input group "=== Session / safety ==="
input int    EODHour = 22;  input int EODMin = 55;
input double MaxDailyLossPct = 2.8;    // catastrophe flatten+halt (0=off; below FTMO 3%)
input ulong  MagicBase = 8850000;

CTrade trade;

#define NLEGS 8
string Tag[NLEGS] = {"A_USORB","B_EUORB","C_VWPULL","D_PDHL","E_FADE","F_TOM","G_MON","H_GER"};
double Stop[NLEGS], TPr[NLEGS], BEr[NLEGS], TrailR[NLEGS], PartR[NLEGS];
bool   g_traded[NLEGS], g_partDone[NLEGS];
double g_extreme[NLEGS];

// ORB state (0=A, 1=B)
double g_rHigh[2], g_rLow[2], g_rVolAvg[2];  bool g_orReady[2];
// PDH/PDL
double g_pdh, g_pdl;  bool g_pdReady;
// VWAP buffers (session from 16:00, reused by legs C and E)
#define MAXB 800
double g_vwap[MAXB], g_close[MAXB], g_low[MAXB], g_high[MAXB], g_dev[MAXB];
int    g_tod[MAXB];  int g_vc;  double g_cumPV, g_cumV;
// regime (leg E): computed once per day from D1
bool   g_rangeRegime = false;
// indicator handles
int    h_adx = INVALID_HANDLE, h_atr = INVALID_HANDLE, h_atrG = INVALID_HANDLE;

datetime g_day = 0, g_lastBar = 0;
double   g_dayStartEquity = 0, g_dayStartBalance = 0;
bool     g_halted = false, g_noNew = false;

//+------------------------------------------------------------------+
int OnInit()
{
   Stop[0]=A_StopPoints; TPr[0]=A_TP_R; BEr[0]=0;      TrailR[0]=0;        PartR[0]=0;
   Stop[1]=B_StopPoints; TPr[1]=B_TP_R; BEr[1]=B_BE_R; TrailR[1]=0;        PartR[1]=0;
   Stop[2]=C_StopPoints; TPr[2]=C_TP_R; BEr[2]=0;      TrailR[2]=0;        PartR[2]=0;
   Stop[3]=D_StopPoints; TPr[3]=0;      BEr[3]=0;      TrailR[3]=D_TrailR; PartR[3]=0;
   Stop[4]=0;            TPr[4]=0;      BEr[4]=0;      TrailR[4]=E_TrailR; PartR[4]=E_PartialR; // stop set daily from ATR
   Stop[5]=F_StopPoints; TPr[5]=0;      BEr[5]=F_BE_R; TrailR[5]=F_TrailR; PartR[5]=0;
   Stop[6]=0;            TPr[6]=0;      BEr[6]=0;      TrailR[6]=0;        PartR[6]=0;           // ATR daily
   Stop[7]=0;            TPr[7]=0;      BEr[7]=0;      TrailR[7]=0;        PartR[7]=0;           // ATR daily
   trade.SetTypeFillingBySymbol(_Symbol);
   h_adx = iADX(_Symbol, PERIOD_D1, 14);
   h_atr = iATR(_Symbol, PERIOD_D1, 14);
   if(UseH) h_atrG = iATR(GER40Symbol, PERIOD_D1, 14);
   PrintFormat("52pPlus v1.0: risk=%.2f%% breaker=-%.1fR A=%d B=%d C=%d D=%d E=%d F=%d G=%d H=%d(%s) EOD=%02d:%02d",
               RiskPercent, DailyBreakerR, UseA,UseB,UseC,UseD,UseE,UseF,UseG,UseH, GER40Symbol, EODHour, EODMin);
   return(INIT_SUCCEEDED);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
double D1ATR(){ double b[]; if(h_atr==INVALID_HANDLE||CopyBuffer(h_atr,0,1,1,b)!=1) return 0; return b[0]; }
double D1ATR_G(){ double b[]; if(h_atrG==INVALID_HANDLE||CopyBuffer(h_atrG,0,1,1,b)!=1) return 0; return b[0]; }
double D1ADX(){ double b[]; if(h_adx==INVALID_HANDLE||CopyBuffer(h_adx,0,1,1,b)!=1) return 99; return b[0]; }

// Choppiness Index(14) on D1, shift 1 (prior completed days only)
double D1Chop()
{
   double sumTR=0, hh=-DBL_MAX, ll=DBL_MAX;
   for(int i=1;i<=14;i++){
      double hi=iHigh(_Symbol,PERIOD_D1,i), lo=iLow(_Symbol,PERIOD_D1,i), pc=iClose(_Symbol,PERIOD_D1,i+1);
      if(hi<=0||lo<=0) return 0;
      double tr=MathMax(hi-lo, MathMax(MathAbs(hi-pc), MathAbs(lo-pc)));
      sumTR+=tr; hh=MathMax(hh,hi); ll=MathMin(ll,lo);
   }
   if(hh<=ll||sumTR<=0) return 0;
   return 100.0*MathLog10(sumTR/(hh-ll))/MathLog10(14.0);
}

// turn-of-month: first 3 trading days of month, or last trading day (next weekday rolls month)
bool IsTomDay(datetime now)
{
   MqlDateTime s; TimeToStruct(now,s);
   // first 3 trading days: count D1 bars this month strictly before today
   int cnt=0;
   for(int i=1;i<=10;i++){
      datetime bt=iTime(_Symbol,PERIOD_D1,i);
      if(bt==0) break;
      MqlDateTime b; TimeToStruct(bt,b);
      if(b.mon==s.mon && b.year==s.year) cnt++;
      else break;
   }
   if(cnt<3) return true;
   // last trading day: next weekday is in a different month (holiday edges approximated)
   datetime nx=now+86400; MqlDateTime n; TimeToStruct(nx,n);
   while(n.day_of_week==0||n.day_of_week==6){ nx+=86400; TimeToStruct(nx,n); }
   return (n.mon!=s.mon);
}

double LotsFor(string sym, double stop_pts)
{
   double riskMon=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0||stop_pts<=0) return 0;
   double lpl=(stop_pts/ts)*tv; if(lpl<=0) return 0;
   double lots=riskMon/lpl;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double mn=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), mx=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   if(lots<mn) lots=mn;  if(lots>mx) lots=mx;
   return lots;
}

bool SelPos(ulong magic, ulong &ticket)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(PositionSelectByTicket(tk) && (ulong)PositionGetInteger(POSITION_MAGIC)==magic){ ticket=tk; return true; }
   }
   return false;
}
void CloseSetup(int s){ ulong tk; if(SelPos(MagicBase+s,tk)){ trade.SetExpertMagicNumber(MagicBase+s); trade.PositionClose(tk);} }

void OpenTrade(int s, string sym, int dir, double stop_pts)
{
   if(g_noNew || stop_pts<=0) return;
   double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
   double px=(dir>0)?ask:bid;  if(px<=0) return;
   double lots=LotsFor(sym,stop_pts);  if(lots<=0) return;
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double sl=(dir>0)?px-stop_pts:px+stop_pts;
   double tp=(TPr[s]>0)?((dir>0)?px+TPr[s]*stop_pts:px-TPr[s]*stop_pts):0.0;
   ulong magic=MagicBase+s; trade.SetExpertMagicNumber(magic);
   bool ok=(dir>0)? trade.Buy(lots,sym,0.0,NormalizeDouble(sl,dg),NormalizeDouble(tp,dg),Tag[s])
                  : trade.Sell(lots,sym,0.0,NormalizeDouble(sl,dg),NormalizeDouble(tp,dg),Tag[s]);
   if(ok){ g_traded[s]=true; g_extreme[s]=px; g_partDone[s]=false; Stop[s]=stop_pts; }
}

// BE / trail / 50% partial (preserving TP)
void ManagePos(int s, string sym)
{
   if(BEr[s]<=0 && TrailR[s]<=0 && PartR[s]<=0) return;
   ulong magic=MagicBase+s, tk;  if(!SelPos(magic,tk)) return;
   long type=PositionGetInteger(POSITION_TYPE);
   double entry=PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL), curTP=PositionGetDouble(POSITION_TP);
   double vol=PositionGetDouble(POSITION_VOLUME);
   double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double stp=Stop[s]; if(stp<=0) return;
   trade.SetExpertMagicNumber(magic);
   if(type==POSITION_TYPE_BUY){
      if(bid>g_extreme[s]) g_extreme[s]=bid;
      if(PartR[s]>0 && !g_partDone[s] && bid-entry>=PartR[s]*stp){
         double half=NormalizeDouble(vol/2.0,2);
         double mnv=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
         if(half>=mnv){ trade.PositionClosePartial(tk,half); g_partDone[s]=true;
            if(SelPos(magic,tk)) trade.PositionModify(tk,NormalizeDouble(entry,dg),curTP); return; }
      }
      double newSL=curSL;
      if(TrailR[s]>0) newSL=MathMax(newSL, g_extreme[s]-TrailR[s]*stp);
      if(BEr[s]>0 && g_extreme[s]-entry>=BEr[s]*stp) newSL=MathMax(newSL, entry);
      if(newSL>curSL+_Point) trade.PositionModify(tk,NormalizeDouble(newSL,dg),curTP);
   } else if(type==POSITION_TYPE_SELL){
      if(g_extreme[s]==0 || ask<g_extreme[s]) g_extreme[s]=ask;
      if(PartR[s]>0 && !g_partDone[s] && entry-ask>=PartR[s]*stp){
         double half=NormalizeDouble(vol/2.0,2);
         double mnv=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
         if(half>=mnv){ trade.PositionClosePartial(tk,half); g_partDone[s]=true;
            if(SelPos(magic,tk)) trade.PositionModify(tk,NormalizeDouble(entry,dg),curTP); return; }
      }
      double newSL=curSL;
      if(TrailR[s]>0){ double t2=g_extreme[s]+TrailR[s]*stp; newSL=(curSL==0)?t2:MathMin(newSL,t2); }
      if(BEr[s]>0 && entry-g_extreme[s]>=BEr[s]*stp) newSL=(newSL==0)?entry:MathMin(newSL,entry);
      if(curSL==0 || newSL<curSL-_Point) trade.PositionModify(tk,NormalizeDouble(newSL,dg),curTP);
   }
}

void ComputeORB(int s, datetime now, int hh, int mm, int orMin)
{
   MqlDateTime st; TimeToStruct(now,st); st.hour=hh; st.min=mm; st.sec=0;
   datetime t0=StructToTime(st), t1=t0+orMin*60;
   if(now<t1) return;
   MqlRates r[]; int n=CopyRates(_Symbol,PERIOD_M1,t0,t1-1,r);
   if(n<(int)(orMin*0.5)) return;
   double hi=-DBL_MAX, lo=DBL_MAX, vs=0;
   for(int j=0;j<n;j++){ if(r[j].high>hi)hi=r[j].high; if(r[j].low<lo)lo=r[j].low; vs+=(double)r[j].tick_volume; }
   if(hi<=lo) return;
   g_rHigh[s]=hi; g_rLow[s]=lo; g_rVolAvg[s]=vs/n; g_orReady[s]=true;
}
bool VolOK(int s){ long vb[]; if(CopyTickVolume(_Symbol,PERIOD_M1,1,1,vb)!=1) return false; return((double)vb[0]>g_rVolAvg[s]); }

void TryORB(int s, datetime now, int hh, int mm, int orMin)
{
   if(g_traded[s]) return;
   if(!g_orReady[s]) ComputeORB(s,now,hh,mm,orMin);
   if(!g_orReady[s]) return;
   ulong tk; if(SelPos(MagicBase+s,tk)) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if((ask>=g_rHigh[s]||bid<=g_rLow[s]) && !VolOK(s)) return;
   if(ask>=g_rHigh[s])      OpenTrade(s,_Symbol,+1,Stop[s]);
   else if(bid<=g_rLow[s])  OpenTrade(s,_Symbol,-1,Stop[s]);
}

void OnTick()
{
   datetime now=TimeCurrent(); MqlDateTime st; TimeToStruct(now,st);
   datetime ds=DayStart(now);
   if(ds!=g_day){
      g_day=ds; g_vc=0; g_cumPV=0; g_cumV=0; g_halted=false; g_noNew=false;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
      g_dayStartBalance=AccountInfoDouble(ACCOUNT_BALANCE);
      for(int s=0;s<NLEGS;s++){ g_traded[s]=false; g_extreme[s]=0; g_partDone[s]=false; }
      g_orReady[0]=false; g_orReady[1]=false; g_pdReady=false;
      double adx=D1ADX(), chop=D1Chop();
      g_rangeRegime=(adx<20.0 && chop>55.0);
      Stop[4]=E_StopATR*D1ATR();  Stop[6]=G_StopATR*D1ATR();
      if(UseH) Stop[7]=H_StopATR*D1ATR_G();
      PrintFormat("52pPlus day: ADX=%.1f Chop=%.1f rangeRegime=%d tom=%d stops E=%.0f G=%.0f H=%.1f",
                  adx, chop, g_rangeRegime, IsTomDay(now), Stop[4], Stop[6], Stop[7]);
   }

   double eq=AccountInfoDouble(ACCOUNT_EQUITY), bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double spread=ask-bid;

   if(DailyBreakerR>0 && g_dayStartBalance>0){
      double rUnit=g_dayStartBalance*RiskPercent/100.0;
      if(rUnit>0 && (bal-g_dayStartBalance)<=-DailyBreakerR*rUnit) g_noNew=true;
   }
   bool dailyBreach=(MaxDailyLossPct>0 && g_dayStartEquity>0 &&
                     (eq-g_dayStartEquity)/g_dayStartEquity*100.0<=-MaxDailyLossPct);
   if(dailyBreach) g_halted=true;
   if(g_halted){ for(int s=0;s<NLEGS;s++) CloseSetup(s); return; }
   // EOD flatten (all legs incl. GER40)
   if(st.hour>EODHour || (st.hour==EODHour && st.min>=EODMin)){ for(int s=0;s<NLEGS;s++) CloseSetup(s); return; }

   // GER40 timed exit 18:45
   if(UseH && (st.hour>H_ExitHour || (st.hour==H_ExitHour && st.min>=H_ExitMin))) CloseSetup(7);

   for(int s=0;s<NLEGS;s++) ManagePos(s, s==7?GER40Symbol:_Symbol);

   // build session VWAP buffers from 16:00 (legs C + E)
   datetime bt=iTime(_Symbol,PERIOD_M1,1);
   bool newBar=(bt!=g_lastBar);
   if(newBar){
      g_lastBar=bt;
      MqlDateTime bs; TimeToStruct(bt,bs);
      if((bs.hour>16 || (bs.hour==16 && bs.min>=0)) && g_vc<MAXB){
         double bh=iHigh(_Symbol,PERIOD_M1,1), bl=iLow(_Symbol,PERIOD_M1,1), bc=iClose(_Symbol,PERIOD_M1,1);
         double bv=(double)iVolume(_Symbol,PERIOD_M1,1); double tpx=(bh+bl+bc)/3.0;
         g_cumPV+=tpx*bv; g_cumV+=bv; double vw=(g_cumV>0)?g_cumPV/g_cumV:bc;
         int j=g_vc; g_vwap[j]=vw; g_close[j]=bc; g_low[j]=bl; g_high[j]=bh;
         g_dev[j]=bc-vw; g_tod[j]=bs.hour*60+bs.min; g_vc++;
      }
   }

   bool canEnter=!g_noNew && (spread<=MaxSpreadPts);
   if(!canEnter) return;

   if(UseA) TryORB(0, now, A_Hour, A_Min, A_ORMinutes);
   if(UseB) TryORB(1, now, B_Hour, B_Min, B_ORMinutes);

   // D: prior-day H/L break
   if(UseD && !g_traded[3] && st.hour>=D_SessHour && st.hour<=D_EntryByHour){
      if(!g_pdReady){ double ph=iHigh(_Symbol,PERIOD_D1,1), pl=iLow(_Symbol,PERIOD_D1,1);
         if(ph>0 && pl>0 && ph>pl){ g_pdh=ph; g_pdl=pl; g_pdReady=true; } }
      ulong tk;
      if(g_pdReady && !SelPos(MagicBase+3,tk)){
         if(ask>=g_pdh+D_Buf)      OpenTrade(3,_Symbol,+1,Stop[3]);
         else if(bid<=g_pdl-D_Buf) OpenTrade(3,_Symbol,-1,Stop[3]);
      }
   }

   // C: VWAP pullback on new closed bar
   if(UseC && newBar && !g_traded[2] && g_vc>C_TrendBars){
      int j=g_vc-1;
      if(g_tod[j] <= C_EntryByHour*60){
         double vw=g_vwap[j];
         bool up=(g_close[j]>vw && vw>g_vwap[j-C_TrendBars]);
         bool dn=(g_close[j]<vw && vw<g_vwap[j-C_TrendBars]);
         if(up && g_low[j]<=vw+C_Buf && g_close[j]>vw)        OpenTrade(2,_Symbol,+1,Stop[2]);
         else if(dn && g_high[j]>=vw-C_Buf && g_close[j]<vw)  OpenTrade(2,_Symbol,-1,Stop[2]);
      }
   }

   // E: VWAP fade, ONLY on range-regime days; flat VWAP; z-stretch; from 16:30
   if(UseE && g_rangeRegime && newBar && !g_traded[4] && g_vc>40 && Stop[4]>0){
      int j=g_vc-1;
      if(g_tod[j]>=16*60+30 && g_tod[j]<=E_EntryByHour*60){
         if(MathAbs(g_vwap[j]-g_vwap[j-40])<=E_FlatPts){
            // rolling std of deviation over last 30 bars
            double m=0; for(int i2=j-29;i2<=j;i2++) m+=g_dev[i2]; m/=30.0;
            double v2=0; for(int i2=j-29;i2<=j;i2++) v2+=(g_dev[i2]-m)*(g_dev[i2]-m);
            double sd=MathSqrt(v2/30.0);
            if(sd>0){
               double z=g_dev[j]/sd;
               if(z>=E_FadeZ)       OpenTrade(4,_Symbol,-1,Stop[4]);
               else if(z<=-E_FadeZ) OpenTrade(4,_Symbol,+1,Stop[4]);
            }
         }
      }
   }

   // F: turn-of-month long at 16:00
   if(UseF && !g_traded[5] && st.hour==16 && st.min<5 && IsTomDay(now))
      OpenTrade(5,_Symbol,+1,Stop[5]);

   // G: Monday long at 16:30
   if(UseG && !g_traded[6] && st.day_of_week==1 && st.hour==16 && st.min>=30 && st.min<35 && Stop[6]>0)
      OpenTrade(6,_Symbol,+1,Stop[6]);

   // H: GER40 long at 18:00 (exits 18:45 above)
   if(UseH && !g_traded[7] && st.hour==H_EntryHour && st.min>=H_EntryMin && st.min<H_EntryMin+5 && Stop[7]>0){
      double gspread=SymbolInfoDouble(GER40Symbol,SYMBOL_ASK)-SymbolInfoDouble(GER40Symbol,SYMBOL_BID);
      if(gspread>0 && gspread<=3.0) OpenTrade(7,GER40Symbol,+1,Stop[7]);
   }
}
//+------------------------------------------------------------------+
