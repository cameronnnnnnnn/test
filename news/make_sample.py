"""
news/make_sample.py — writes sample_catalog.csv, a SYNTHETIC file in the EXACT format the
ForexFactoryScraper produces (headerless: datetime(EST tz-aware), currency, impact, event,
actual, forecast, previous). The dates/values are RANDOM — this is only to prove the newsbank
pipeline runs against the real NAS data. Replace it with the real forex_factory_catalog.csv.
Run: python3 make_sample.py   then   python3 newsbank.py sample_catalog.csv "CPI m/m"
"""
import csv
import numpy as np, pandas as pd

rng = np.random.default_rng(1)
lo = pd.Timestamp("2022-10-18", tz="US/Eastern"); hi = pd.Timestamp("2025-10-01", tz="US/Eastern")
rows = []
for y in range(2022, 2026):
    for mo in range(1, 13):
        for day, ev in [(12, "CPI m/m"), (7, "Non-Farm Employment Change")]:
            t = pd.Timestamp(year=y, month=mo, day=day, hour=8, minute=30, tz="US/Eastern")
            if not (lo <= t <= hi):
                continue
            if ev.startswith("CPI"):
                fc = round(float(rng.uniform(0.1, 0.5)), 1)
                ac = round(fc + float(rng.choice([-0.2, -0.1, 0, 0.1, 0.2])), 1)
                rows.append([str(t), "USD", "High Impact Expected", ev, f"{ac}%", f"{fc}%", f"{fc}%"])
            else:
                fc = int(rng.uniform(120, 260)); ac = int(fc + rng.normal(0, 60))
                rows.append([str(t), "USD", "High Impact Expected", ev, f"{ac}K", f"{fc}K", f"{fc}K"])
with open("sample_catalog.csv", "w", newline="") as f:
    csv.writer(f).writerows(rows)
print(f"wrote {len(rows)} SYNTHETIC rows -> sample_catalog.csv (fake data, format-only)")
