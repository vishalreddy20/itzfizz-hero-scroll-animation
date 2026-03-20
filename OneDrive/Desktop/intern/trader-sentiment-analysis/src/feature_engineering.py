"""Feature engineering for daily metrics and trader profiles."""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _closed_trade_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Prefer closed trades for performance metrics to avoid zero-pnl dilution."""
    out = df.copy()
    if "is_closed_trade" in out.columns:
        closed = out.loc[out["is_closed_trade"] == 1].copy()
        if not closed.empty:
            return closed
    closed = out.loc[out["closedPnL"] != 0].copy()
    return closed if not closed.empty else out


def build_daily_summary(merged_df: pd.DataFrame) -> pd.DataFrame:
    """Create a daily aggregated summary merged with sentiment.

    Args:
        merged_df: Trade-level merged dataframe.

    Returns:
        Daily summary dataframe.
    """
    df = _closed_trade_subset(merged_df)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    long_short_daily = (
        df.assign(is_long=(df["side"] == "LONG").astype(int), is_short=(df["side"] == "SHORT").astype(int))
        .groupby("date", as_index=False)[["is_long", "is_short"]]
        .sum()
    )
    long_short_daily["long_short_ratio"] = long_short_daily["is_long"] / long_short_daily[
        "is_short"
    ].replace(0, np.nan)

    daily = (
        df.groupby("date", as_index=False)
        .agg(
            daily_total_pnl=("closedPnL", "sum"),
            daily_avg_pnl=("closedPnL", "mean"),
            daily_median_pnl=("closedPnL", "median"),
            daily_win_rate=("is_profitable", "mean"),
            daily_trade_count=("closedPnL", "size"),
            daily_avg_leverage=("leverage", "mean"),
            sentiment_score=("sentiment_score", "mean"),
        )
        .merge(long_short_daily[["date", "long_short_ratio"]], on="date", how="left")
    )

    sentiment_labels = (
        df.dropna(subset=["date", "sentiment_label"])
        .groupby("date")["sentiment_label"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
        .reset_index()
    )
    daily = daily.merge(sentiment_labels, on="date", how="left")
    logger.info("Built daily summary with %d rows", len(daily))
    return daily


def build_trader_features(merged_df: pd.DataFrame) -> pd.DataFrame:
    """Build trader-level features for clustering analysis.

    Args:
        merged_df: Trade-level merged dataframe.

    Returns:
        Trader feature dataframe.
    """
    df = merged_df.copy()

    base = df.groupby("account", as_index=False).agg(
        trade_count=("closedPnL", "size"),
        win_rate=("is_profitable", "mean"),
        avg_pnl_per_trade=("closedPnL", "mean"),
        avg_leverage=("leverage", "mean"),
        cumulative_pnl=("closedPnL", "sum"),
    )

    long_pref = (
        df.assign(is_long=(df["side"] == "LONG").astype(int))
        .groupby("account", as_index=False)["is_long"]
        .mean()
        .rename(columns={"is_long": "long_preference"})
    )

    fear_activity = (
        df.assign(is_fear=df["sentiment_label"].isin(["Fear", "Extreme Fear"]).astype(int))
        .groupby("account", as_index=False)["is_fear"]
        .mean()
        .rename(columns={"is_fear": "fear_activity_ratio"})
    )

    greed_activity = (
        df.assign(is_greed=df["sentiment_label"].isin(["Greed", "Extreme Greed"]).astype(int))
        .groupby("account", as_index=False)["is_greed"]
        .mean()
        .rename(columns={"is_greed": "greed_activity_ratio"})
    )

    features = (
        base.merge(long_pref, on="account", how="left")
        .merge(fear_activity, on="account", how="left")
        .merge(greed_activity, on="account", how="left")
    )

    return features


def summarize_by_sentiment(merged_df: pd.DataFrame) -> pd.DataFrame:
    """Build grouped metrics by sentiment class.

    Args:
        merged_df: Trade-level merged dataframe.

    Returns:
        Sentiment summary table.
    """
    df = _closed_trade_subset(merged_df)

    summary = (
        df.dropna(subset=["sentiment_label"])
        .groupby("sentiment_label", as_index=False)
        .agg(
            mean_pnl=("closedPnL", "mean"),
            median_pnl=("closedPnL", "median"),
            win_rate=("is_profitable", "mean"),
            trade_count=("closedPnL", "size"),
            avg_leverage=("leverage", "mean"),
            avg_position_size_usd=("position_size_usd", "mean"),
            long_ratio=("side", lambda s: (s == "LONG").mean()),
            short_ratio=("side", lambda s: (s == "SHORT").mean()),
        )
    )

    order: Dict[str, int] = {
        "Extreme Fear": 1,
        "Fear": 2,
        "Neutral": 3,
        "Greed": 4,
        "Extreme Greed": 5,
    }

    summary["sort_key"] = summary["sentiment_label"].map(order)
    summary = summary.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)
    return summary
