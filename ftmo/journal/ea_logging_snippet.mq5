//+------------------------------------------------------------------+
//| ORB journal logging — paste into NAS100_ORB_sprint.mq5            |
//| Appends every CLOSED position to MQL5/Files/ORB_journal.csv in    |
//| the exact format orb_journal.py ingests. Recompile + re-attach    |
//| while the market is closed so you don't interrupt a live trade.   |
//+------------------------------------------------------------------+

// 1) add these inputs near the top of the file:
input bool   LogTrades = true;                 // write closed trades to CSV
input string LogFile   = "ORB_journal.csv";    // lands in MQL5/Files/

// 2) call EnsureJournalHeader(); at the END of OnInit():
void EnsureJournalHeader()
{
   if(!LogTrades) return;
   if(!FileIsExist(LogFile))
   {
      int h=FileOpen(LogFile,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
      if(h!=INVALID_HANDLE)
      {
         FileWrite(h,"ticket","symbol","type","volume","open_time","open_price",
                     "close_time","close_price","sl","profit","commission","swap","comment");
         FileClose(h);
      }
   }
}

// 3) add this whole function anywhere at file scope:
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(!LogTrades) return;
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD) return;

   ulong deal=trans.deal;
   if(!HistoryDealSelect(deal)) return;
   if(HistoryDealGetInteger(deal,DEAL_ENTRY)!=DEAL_ENTRY_OUT) return;  // only on close

   long     posid  = HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   double   cprice = HistoryDealGetDouble (deal,DEAL_PRICE);
   datetime ctime  = (datetime)HistoryDealGetInteger(deal,DEAL_TIME);
   double   profit = HistoryDealGetDouble (deal,DEAL_PROFIT);
   double   comm   = HistoryDealGetDouble (deal,DEAL_COMMISSION);
   double   swp    = HistoryDealGetDouble (deal,DEAL_SWAP);
   double   vol    = HistoryDealGetDouble (deal,DEAL_VOLUME);
   string   sym    = HistoryDealGetString (deal,DEAL_SYMBOL);
   string   comment= HistoryDealGetString (deal,DEAL_COMMENT);

   // pull the opening deal for this position (entry price/time/direction)
   double   oprice=0.0; datetime otime=0; string otype="";
   if(HistorySelectByPosition(posid))
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong d=HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_IN)
         {
            oprice=HistoryDealGetDouble(d,DEAL_PRICE);
            otime =(datetime)HistoryDealGetInteger(d,DEAL_TIME);
            otype =(HistoryDealGetInteger(d,DEAL_TYPE)==DEAL_TYPE_BUY)?"buy":"sell";
            if(comment=="") comment=HistoryDealGetString(d,DEAL_COMMENT);
         }
      }

   int h=FileOpen(LogFile,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) return;
   FileSeek(h,0,SEEK_END);
   FileWrite(h,(long)posid,sym,otype,vol,
             TimeToString(otime,TIME_DATE|TIME_SECONDS),oprice,
             TimeToString(ctime,TIME_DATE|TIME_SECONDS),cprice,
             0.0,profit,comm,swp,comment);
   FileClose(h);
}
