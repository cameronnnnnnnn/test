"""
Build clean EURUSD / GBPUSD daily price series from legitimate real data.

Source: U.S. Federal Reserve H.10 noon buying rates, published on FRED
(DEXUSEU = US$/EUR, DEXUSUK = US$/GBP), mirrored on GitHub by the
datahub.io 'core/exchange-rates' dataset:
  https://github.com/datasets/exchange-rates  (file data/daily.csv)

The datahub file quotes FOREIGN currency per 1 USD, so we invert to get the
conventional EURUSD and GBPUSD quotes (USD per 1 unit of foreign currency).
This is genuine published central-bank reference data - NOT synthetic.

Limitation (stated honestly): one rate per business day, no intraday OHLC and
no bid/ask spread. Backtest is therefore close-to-close on daily bars with an
explicit spread/slippage cost applied to every fill.
"""
import pandas as pd

RAW = "ftmo/fred_daily_raw.csv"
OUT = "ftmo/prices.csv"

df = pd.read_csv(RAW)
df["Date"] = pd.to_datetime(df["Date"])

eur = df[df["Country"] == "Euro"][["Date", "Exchange rate"]].copy()
gbp = df[df["Country"] == "United Kingdom"][["Date", "Exchange rate"]].copy()

# datahub 'Exchange rate' = foreign units per USD -> invert to USD per unit
eur["EURUSD"] = 1.0 / eur["Exchange rate"]
gbp["GBPUSD"] = 1.0 / gbp["Exchange rate"]

m = pd.merge(eur[["Date", "EURUSD"]], gbp[["Date", "GBPUSD"]], on="Date", how="inner")
m = m.sort_values("Date").reset_index(drop=True)

# FRED uses '.' / blanks for holidays -> drop non-numeric, forward nothing
m = m.dropna()
m = m[(m["EURUSD"] > 0.5) & (m["EURUSD"] < 2.0)]
m = m[(m["GBPUSD"] > 0.5) & (m["GBPUSD"] < 3.0)]

# Past 5 years
end = m["Date"].max()
start = end - pd.DateOffset(years=5)
m = m[m["Date"] >= start].reset_index(drop=True)

m.to_csv(OUT, index=False)
print(f"rows: {len(m)}")
print(f"range: {m['Date'].min().date()} -> {m['Date'].max().date()}")
print(m.head(3).to_string(index=False))
print(m.tail(3).to_string(index=False))
print(f"EURUSD min/max: {m['EURUSD'].min():.4f} / {m['EURUSD'].max():.4f}")
print(f"GBPUSD min/max: {m['GBPUSD'].min():.4f} / {m['GBPUSD'].max():.4f}")
