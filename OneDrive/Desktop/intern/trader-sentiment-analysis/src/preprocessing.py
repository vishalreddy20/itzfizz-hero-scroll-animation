"""Preprocessing pipeline for sentiment and trader datasets."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


SENTIMENT_MAP: Dict[str, int] = {
    "Extreme Fear": 1,
    "Fear": 2,
    "Neutral": 3,
    "Greed": 4,
    "Extreme Greed": 5,
}


def _normalize_col(col: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", col.strip().lower())


def standardize_trade_columns(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Rename diverse raw trade column names to standardized names.

    Args:
        trades_df: Raw trades dataframe.

    Returns:
        Dataframe with standardized columns.
    """
    df = trades_df.copy()
    source_cols = {col: _normalize_col(col) for col in df.columns}

    reverse = {v: k for k, v in source_cols.items()}

    mapped = {}

    if "account" in reverse:
        mapped[reverse["account"]] = "account"
    if "symbol" in reverse:
        mapped[reverse["symbol"]] = "symbol"
    elif "coin" in reverse:
        mapped[reverse["coin"]] = "symbol"

    if "executionprice" in reverse:
        mapped[reverse["executionprice"]] = "execution_price"

    if "size" in reverse:
        mapped[reverse["size"]] = "size"
    elif "sizetokens" in reverse:
        mapped[reverse["sizetokens"]] = "size"

    if "side" in reverse:
        mapped[reverse["side"]] = "side"
    elif "direction" in reverse:
        mapped[reverse["direction"]] = "side"

    if "time" in reverse:
        mapped[reverse["time"]] = "time"
    elif "timestampist" in reverse:
        mapped[reverse["timestampist"]] = "time"

    if "startposition" in reverse:
        mapped[reverse["startposition"]] = "start_position"

    if "event" in reverse:
        mapped[reverse["event"]] = "event"

    if "closedpnl" in reverse:
        mapped[reverse["closedpnl"]] = "closedPnL"

    if "leverage" in reverse:
        mapped[reverse["leverage"]] = "leverage"

    df = df.rename(columns=mapped)
    return df


def preprocess_fear_greed(fear_greed_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Clean and validate fear-greed dataset.

    Args:
        fear_greed_df: Raw fear-greed dataframe.

    Returns:
        Tuple with (cleaned_dataframe, diagnostics_dataframe).
    """
    df = fear_greed_df.copy()

    if "Date" in df.columns:
        date_col = "Date"
    elif "date" in df.columns:
        date_col = "date"
    else:
        raise ValueError("Could not find Date/date column in fear-greed data")

    if "Classification" in df.columns:
        class_col = "Classification"
    elif "classification" in df.columns:
        class_col = "classification"
    else:
        raise ValueError("Could not find Classification/classification column")

    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["Classification"] = df[class_col].astype(str).str.strip()
    df["sentiment_score"] = df["Classification"].map(SENTIMENT_MAP)

    null_count = int(df.isna().sum().sum())
    dup_count = int(df.duplicated(subset=["Date", "Classification"]).sum())

    date_range = pd.date_range(df["Date"].min(), df["Date"].max(), freq="D")
    missing_dates = date_range.difference(df["Date"].dropna().sort_values())

    diagnostics = pd.DataFrame(
        {
            "metric": ["null_cells", "duplicate_rows", "date_gaps"],
            "value": [null_count, dup_count, int(len(missing_dates))],
        }
    )

    df = df.dropna(subset=["Date", "Classification"]).drop_duplicates(
        subset=["Date", "Classification"]
    )
    df = df.sort_values("Date").reset_index(drop=True)

    logger.info(
        "Fear-greed cleaned rows=%d null_cells=%d duplicates=%d date_gaps=%d",
        len(df),
        null_count,
        dup_count,
        len(missing_dates),
    )

    return df, diagnostics


def preprocess_trades(trades_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Clean and enrich trades dataframe.

    Args:
        trades_df: Raw trades dataframe.

    Returns:
        Tuple with (cleaned_dataframe, quarantine_dataframe).
    """
    df = standardize_trade_columns(trades_df)
    df = df.copy()

    if "time" not in df.columns:
        raise ValueError("Could not map a time column in trade data")

    df["time"] = pd.to_datetime(df["time"], dayfirst=True, errors="coerce")

    for col in ["closedPnL", "size", "execution_price", "leverage", "start_position"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "closedPnL" not in df.columns:
        df["closedPnL"] = 0.0
    df["closedPnL"] = df["closedPnL"].fillna(0.0)

    if "side" in df.columns:
        side_norm = df["side"].astype(str).str.strip().str.upper()
        side_norm = side_norm.replace({"BUY": "LONG", "SELL": "SHORT"})
        side_norm = np.where(side_norm.str.contains("LONG"), "LONG", side_norm)
        side_norm = np.where(pd.Series(side_norm).str.contains("SHORT"), "SHORT", side_norm)
        df["side"] = pd.Series(side_norm, index=df.index)
    else:
        df["side"] = "UNKNOWN"

    # Record impossible rows then remove from analysis set.
    bad_mask = (
        df["size"].fillna(-1) <= 0
        if "size" in df.columns
        else pd.Series([True] * len(df), index=df.index)
    ) | (
        df["execution_price"].fillna(-1) <= 0
        if "execution_price" in df.columns
        else pd.Series([True] * len(df), index=df.index)
    )

    quarantine_df = df.loc[bad_mask].copy()
    cleaned = df.loc[~bad_mask].copy()

    cleaned["date"] = cleaned["time"].dt.date
    cleaned["hour"] = cleaned["time"].dt.hour
    cleaned["day_of_week"] = cleaned["time"].dt.day_name()
    cleaned["week"] = cleaned["time"].dt.isocalendar().week.astype("int64")
    cleaned["month"] = cleaned["time"].dt.to_period("M").astype(str)

    cleaned["position_size_usd"] = cleaned["execution_price"] * cleaned["size"]

    # Keep leverage grounded in explicit source data. If missing, use a neutral default.
    if "leverage" not in cleaned.columns:
        cleaned["leverage"] = np.nan
    cleaned["leverage"] = pd.to_numeric(cleaned["leverage"], errors="coerce")
    cleaned["leverage_source"] = np.where(cleaned["leverage"].notna(), "reported", "default_1x")
    cleaned["leverage"] = cleaned["leverage"].fillna(1.0).clip(lower=0, upper=100)

    denom = cleaned["position_size_usd"].replace(0, np.nan)
    cleaned["trade_return_pct"] = (cleaned["closedPnL"] / denom) * 100.0
    cleaned["trade_return_pct"] = cleaned["trade_return_pct"].replace(
        [np.inf, -np.inf], np.nan
    )
    cleaned["is_profitable"] = (cleaned["closedPnL"] > 0).astype(int)
    cleaned["is_closed_trade"] = (cleaned["closedPnL"] != 0).astype(int)

    logger.info(
        "Trades cleaned rows=%d quarantine=%d closed_trade_pct=%.2f",
        len(cleaned),
        len(quarantine_df),
        cleaned["is_closed_trade"].mean() * 100,
    )

    return cleaned, quarantine_df


def merge_datasets(trades_df: pd.DataFrame, fear_greed_df: pd.DataFrame) -> pd.DataFrame:
    """Merge cleaned trades with fear-greed records on date.

    Args:
        trades_df: Cleaned trades dataframe.
        fear_greed_df: Cleaned fear-greed dataframe.

    Returns:
        Merged dataframe.
    """
    trades = trades_df.copy()
    sentiment = fear_greed_df.copy()

    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.normalize()
    sentiment["Date"] = pd.to_datetime(sentiment["Date"], errors="coerce").dt.normalize()

    merged = trades.merge(
        sentiment[["Date", "Classification", "sentiment_score"]],
        left_on="date",
        right_on="Date",
        how="left",
    )

    merged = merged.rename(columns={"Classification": "sentiment_label"})
    return merged


def save_processed_dataset(merged_df: pd.DataFrame, output_path: Path | str) -> None:
    """Persist processed merged dataset to CSV.

    Args:
        merged_df: Final merged dataframe.
        output_path: Output CSV path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(output_path, index=False)
    logger.info("Saved merged dataset to %s", output_path)
