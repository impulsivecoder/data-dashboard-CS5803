"""
One-time aggregation: hotel_bookings.csv -> three small parquet files.

Run locally once after placing hotel_bookings.csv in data/. The committed
parquet files are what the deployed Shiny app actually reads, so the app
never has to load the 16 MB raw CSV at startup.

Aggregates produced (matching the original Tableau workbook):
    1. data/segment_matrix.csv   - bubble chart (hotel x market_segment)
    2. data/adr_by_month.csv     - line chart  (hotel x month)
    3. data/cancel_by_lead.csv   - bar chart   (hotel x lead-time band)

CSV (not parquet) is used because the aggregates are tiny (~3 KB combined)
and CSV avoids a pyarrow dependency, which has caused build failures on
Render's free tier when no matching wheel exists for the runtime Python
version.

Tableau calc fields replicated here verbatim:
    Cancellation Rate %   = SUM(is_canceled) / COUNT(is_canceled) * 100
    Total Bookings        = COUNT(hotel)
    Lead time band        = bucketed lead_time (5 bands as in the workbook)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
RAW_CSV = DATA_DIR / "hotel_bookings.csv"

# Same five buckets as the [Lead time band] calc field in the .twb
LEAD_BAND_EDGES = [-1, 90, 180, 270, 365, float("inf")]
LEAD_BAND_LABELS = ["0-90 days", "90-180 days", "180-270 days",
                    "270-365 days", "365+ days"]

MONTH_ORDER = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# Tableau dashboard hides these two segments (Complementary is ~0.6%
# of bookings, Undefined is 2 rows). Excluding here keeps the bubble
# chart visually identical to the screenshot.
EXCLUDED_SEGMENTS = {"Complementary", "Undefined"}


def load_raw() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise FileNotFoundError(
            f"Expected raw CSV at {RAW_CSV}. Download hotel_bookings.csv "
            "and place it there before running this script."
        )
    df = pd.read_csv(RAW_CSV)
    # Drop the segments the Tableau dashboard filters out
    df = df[~df["market_segment"].isin(EXCLUDED_SEGMENTS)].copy()
    return df


def build_segment_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Bubble chart source: one row per hotel x market_segment."""
    g = df.groupby(["hotel", "market_segment"], as_index=False).agg(
        bookings=("hotel", "size"),
        cancellation_rate=("is_canceled", lambda s: s.mean() * 100),
        avg_adr=("adr", "mean"),
    )
    return g


def build_adr_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Line chart source: one row per hotel x month, ordered Jan..Dec."""
    g = df.groupby(["hotel", "arrival_date_month"], as_index=False).agg(
        avg_adr=("adr", "mean"),
    )
    g["month_num"] = g["arrival_date_month"].map(
        {m: i + 1 for i, m in enumerate(MONTH_ORDER)}
    )
    g = g.sort_values(["hotel", "month_num"]).reset_index(drop=True)
    return g


def build_cancel_by_lead(df: pd.DataFrame) -> pd.DataFrame:
    """Bar chart source: one row per hotel x lead-time band."""
    df = df.copy()
    df["lead_band"] = pd.cut(
        df["lead_time"],
        bins=LEAD_BAND_EDGES,
        labels=LEAD_BAND_LABELS,
        ordered=True,
    )
    g = df.groupby(["hotel", "lead_band"], as_index=False, observed=True).agg(
        cancellation_rate=("is_canceled", lambda s: s.mean() * 100),
        bookings=("hotel", "size"),
    )
    # Preserve band order for plotting
    g["lead_band"] = pd.Categorical(
        g["lead_band"], categories=LEAD_BAND_LABELS, ordered=True
    )
    g = g.sort_values(["lead_band", "hotel"]).reset_index(drop=True)
    return g


def main() -> None:
    df = load_raw()
    print(f"Loaded {len(df):,} rows after filtering excluded segments.")

    segment = build_segment_matrix(df)
    monthly = build_adr_by_month(df)
    leadtime = build_cancel_by_lead(df)

    segment.to_csv(DATA_DIR / "segment_matrix.csv", index=False)
    monthly.to_csv(DATA_DIR / "adr_by_month.csv", index=False)
    leadtime.to_csv(DATA_DIR / "cancel_by_lead.csv", index=False)

    print("\nSegment matrix preview:")
    print(segment.to_string(index=False))
    print("\nADR by month preview:")
    print(monthly.to_string(index=False))
    print("\nCancellation by lead-time band preview:")
    print(leadtime.to_string(index=False))


if __name__ == "__main__":
    main()
