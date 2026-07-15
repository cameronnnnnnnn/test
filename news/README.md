# news/ — economic-calendar bank aligned to the NAS100 M1 data

Answer questions like *"what % of CPI releases were bullish for NAS?"* — overall, by time
horizon, and split by whether the print beat or missed forecast. Built to consume the CSV that
**ForexFactoryScraper** (`ForexFactoryScraper-master/ffs.py`) produces.

## Why you have to run the scraper (I can't fetch it here)
This sandbox's network is locked to package registries only — the proxy returns **403** to
forexfactory.com *and* every alternative (FRED, Nasdaq). And the scraper needs a real,
non-headless Chrome (ForexFactory uses Cloudflare). So the news data has to come from **your**
machine. The alignment engine below is finished and tested; it just needs the file.

## Get the data (on your PC, ~5 min)
```
cd ForexFactoryScraper-master
pip install -r requirements.txt
python ffs.py            # opens Chrome, scrapes Jan-2007 → today, writes forex_factory_catalog.csv
```
Then upload `forex_factory_catalog.csv` here. (Only the rows inside the NAS window,
**2022-10-18 → 2025-10-01**, can be aligned; the rest is ignored.)

## Use it
```
pip install tzdata                                   # this env has no system IANA tz db
python3 newsbank.py forex_factory_catalog.csv                 # summary of the big USD events
python3 newsbank.py forex_factory_catalog.csv "CPI m/m"       # one event, all horizons + surprise
```
From Python:
```python
from newsbank import Bank
b = Bank("forex_factory_catalog.csv")
b.reaction("CPI", horizon=30)          # % bullish, mean/median move, HOT vs MISS split
b.reaction("Non-Farm Employment Change", horizon=15)
b.reaction("Federal Funds Rate")       # FOMC
b.summary()                            # CPI, Core CPI, NFP, FOMC, PPI, Retail Sales, ...
```

## How the alignment works
* The scraper stamps each event in **EST/EDT** (tz-aware, offset embedded). The NAS M1 data is
  naive **server (EET/EEST)** time. `newsbank` parses the offset → UTC → server wall time, so
  an 8:30 ET print lands at ~15:30 server (stable year-round — US & EU shift together).
* For each event it takes the NAS close just before the release (`px0`) and the close `H` minutes
  later, for `H ∈ {5,15,30,60}` → move in points and %. **Bullish = move > 0.**
* `actual`/`forecast`/`previous` are parsed to numbers (`3.7%`→3.7, `236K`→236000); `surprise =
  actual − forecast` drives the HOT / MISS / INLINE split, which is what reveals the real
  print→reaction relationship (e.g. hot CPI → NAS down).

## Files
* `newsbank.py` — the engine (`Bank` class + CLI). **Done, tested against the real NAS data.**
* `make_sample.py` — writes `sample_catalog.csv`, a SYNTHETIC format-only fixture (random dates/
  values) so the pipeline can be run without the real file. **Not real data.**

## Test window (proven)
Ran on 70 synthetic events → all aligned to the NAS window, produced bullish% / mean-move /
HOT-vs-MISS tables at every horizon. Swap in the real CSV and the numbers become meaningful.

Caveat: server-tz assumed **Europe/Bucharest** (FTMO/EET-EEST). If your M1 feed's server clock
differs, the release bar can be off by an hour during the ~2-week US/EU DST-changeover gaps;
everything else is exact.
