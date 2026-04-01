"""Debug walk-forward date filtering."""

import pickle
from datetime import date
from zoneinfo import ZoneInfo

et = ZoneInfo("America/New_York")
bars = pickle.load(open("alphaedge/cache/EURUSD_1_day.pkl", "rb"))  # noqa: SIM115
print(f"Total bars: {len(bars)}")

b0 = bars[0]
print(f"Bar keys: {list(b0.keys())}")
dt0 = b0["datetime"]
print(
    "First bar datetime: "
    f"{dt0}  type={type(dt0).__name__}  "
    f"tzinfo={getattr(dt0, 'tzinfo', 'NO_ATTR')}"
)

b_last = bars[-1]
dt_last = b_last["datetime"]
print(f"Last  bar datetime: {dt_last}  type={type(dt_last).__name__}")

# Simulate _filter_bars_by_date for OOS window Oct-Dec 2024
start_date = date(2024, 10, 1)
end_date = date(2024, 12, 31)
found = []
for bar in bars:
    dt_val = bar["datetime"]
    if hasattr(dt_val, "tzinfo") and dt_val.tzinfo is None:
        dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
    if hasattr(dt_val, "astimezone"):
        bar_date = dt_val.astimezone(et).date()
    else:
        bar_date = dt_val  # already a date
    if start_date <= bar_date <= end_date:
        found.append(bar_date)

print(f"\nOOS Oct-Dec 2024: {len(found)} bars found")
if found:
    print(f"  First: {found[0]}  Last: {found[-1]}")
else:
    # Show what dates are available around that period
    print("No bars found — sampling nearby dates:")
    from alphaedge.engine.walk_forward import _extract_data_range

    data_range = _extract_data_range(bars)
    print(f"  data_range from _extract_data_range: {data_range}")
    # Sample 5 bars around index 400-410
    for bar in bars[380:390]:
        dt_val = bar["datetime"]
        if hasattr(dt_val, "tzinfo") and dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=ZoneInfo("UTC"))
        if hasattr(dt_val, "astimezone"):
            bar_date = dt_val.astimezone(et).date()
        else:
            bar_date = dt_val
        print(f"  bar[380+]: raw={bar['datetime']}  ET date={bar_date}")
