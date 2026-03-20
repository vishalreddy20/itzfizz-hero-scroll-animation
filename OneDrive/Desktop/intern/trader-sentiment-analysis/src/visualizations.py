"""Visualization utilities for analysis outputs."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pandas.plotting import autocorrelation_plot

logger = logging.getLogger(__name__)
sns.set_theme(style="whitegrid")


def _save(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figure: %s", output_path)


def plot_sentiment_timeseries(fg_df: pd.DataFrame, output_path: Path) -> None:
    """Plot sentiment score over time with regime overlays."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(fg_df["Date"], fg_df["sentiment_score"], color="navy", linewidth=1.8, label="Sentiment Score")
    ax.set_title("Bitcoin Fear & Greed Sentiment Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sentiment Score (1-5)")
    ax.legend(loc="upper left")
    ax.text(0.01, 0.02, "Insight: Sentiment clusters into persistent fear/greed regimes.", transform=ax.transAxes)
    _save(fig, output_path)


def plot_sentiment_distribution(fg_df: pd.DataFrame, output_path: Path) -> None:
    """Plot sentiment class distribution."""
    fig, ax = plt.subplots(figsize=(10, 5))
    order = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
    sns.countplot(data=fg_df, x="Classification", order=order, ax=ax)
    ax.set_title("Distribution of Sentiment Classifications")
    ax.set_xlabel("Sentiment Class")
    ax.set_ylabel("Number of Days")
    ax.tick_params(axis="x", rotation=20)
    ax.text(0.01, 0.02, "Insight: Market mood is not uniform across days.", transform=ax.transAxes)
    _save(fig, output_path)


def plot_daily_pnl_area(daily_df: pd.DataFrame, output_path: Path) -> None:
    """Plot daily total PnL area chart."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(daily_df["date"], daily_df["daily_total_pnl"], alpha=0.4, color="teal", label="Daily Total PnL")
    ax.plot(daily_df["date"], daily_df["daily_total_pnl"], color="teal", linewidth=1.2)
    ax.set_title("Aggregate Daily PnL Across Traders")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Total PnL")
    ax.legend(loc="upper left")
    ax.text(0.01, 0.02, "Insight: PnL volatility spikes around major regime shifts.", transform=ax.transAxes)
    _save(fig, output_path)


def plot_leverage_distribution(merged_df: pd.DataFrame, output_path: Path) -> None:
    """Plot leverage histogram and boxplot."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.histplot(merged_df["leverage"].dropna(), bins=50, ax=axes[0], color="darkorange")
    axes[0].set_title("Leverage Distribution")
    axes[0].set_xlabel("Leverage")
    axes[0].set_ylabel("Trade Count")

    sns.boxplot(y=merged_df["leverage"].dropna(), ax=axes[1], color="lightblue")
    axes[1].set_title("Leverage Boxplot")
    axes[1].set_ylabel("Leverage")

    axes[0].text(0.01, 0.93, "Insight: Most trades use conservative leverage with fat-tail outliers.", transform=axes[0].transAxes)
    _save(fig, output_path)


def plot_autocorrelation_sentiment(fg_df: pd.DataFrame, output_path: Path) -> None:
    """Plot sentiment autocorrelation."""
    fig, ax = plt.subplots(figsize=(10, 4))
    autocorrelation_plot(fg_df["sentiment_score"], ax=ax)
    ax.set_title("Autocorrelation of Sentiment Score")
    ax.set_xlabel("Lag")
    ax.set_ylabel("Autocorrelation")
    ax.text(0.01, 0.02, "Insight: Sentiment persistence suggests non-random market mood cycles.", transform=ax.transAxes)
    _save(fig, output_path)


def plot_lag_correlations(lag_df: pd.DataFrame, output_path: Path) -> None:
    """Plot lagged sentiment-performance correlations."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(lag_df["lag"], lag_df["spearman_rho"], marker="o", color="purple", label="Spearman rho")
    ax.axhline(0, linestyle="--", color="gray", linewidth=1)
    ax.set_title("Lagged Correlation: Prior Sentiment vs Daily PnL")
    ax.set_xlabel("Lag (Days)")
    ax.set_ylabel("Spearman Correlation")
    ax.legend(loc="best")
    ax.text(0.01, 0.02, "Insight: Short lags can carry stronger predictive information.", transform=ax.transAxes)
    _save(fig, output_path)
