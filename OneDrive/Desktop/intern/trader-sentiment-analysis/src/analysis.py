"""Statistical analysis and discovery modules."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import kruskal, spearmanr
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def run_kruskal_wallis_pnl_by_sentiment(merged_df: pd.DataFrame) -> Dict[str, float]:
    """Run Kruskal-Wallis test on closed PnL across sentiment groups.

    Args:
        merged_df: Trade-level merged dataframe.

    Returns:
        Dict with test statistic and p-value.
    """
    groups: List[np.ndarray] = []
    for label in ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]:
        vals = merged_df.loc[merged_df["sentiment_label"] == label, "closedPnL"].dropna().values
        if len(vals) > 0:
            groups.append(vals)

    if len(groups) < 2:
        return {"statistic": np.nan, "p_value": np.nan, "epsilon_squared": np.nan}

    stat, p_value = kruskal(*groups)
    n_total = float(sum(len(g) for g in groups))
    k_groups = float(len(groups))
    eps_sq = (stat - k_groups + 1) / (n_total - k_groups) if n_total > k_groups else np.nan
    return {
        "statistic": float(stat),
        "p_value": float(p_value),
        "epsilon_squared": float(eps_sq),
    }


def run_spearman_tests(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Compute Spearman correlation against sentiment score.

    Args:
        daily_df: Daily summary dataframe.

    Returns:
        Dataframe of metric, rho, and p-value.
    """
    rows = []
    for metric in ["daily_avg_pnl", "daily_win_rate", "daily_avg_leverage"]:
        subset = daily_df[["sentiment_score", metric]].dropna()
        if len(subset) < 3 or subset[metric].nunique(dropna=True) < 2:
            rows.append({"metric": metric, "spearman_rho": np.nan, "p_value": np.nan})
            continue
        rho, p_value = spearmanr(subset["sentiment_score"], subset[metric])
        rows.append({"metric": metric, "spearman_rho": float(rho), "p_value": float(p_value)})

    return pd.DataFrame(rows)


def trader_concentration_metrics(merged_df: pd.DataFrame) -> Dict[str, float]:
    """Measure concentration risk in trader-level PnL contributions."""
    df = merged_df.copy()
    trader_pnl = df.groupby("account", as_index=False).agg(total_pnl=("closedPnL", "sum"))
    total = trader_pnl["total_pnl"].sum()
    if total == 0:
        return {"top1_share": np.nan, "top3_share": np.nan, "top5_share": np.nan}

    ranked = trader_pnl.sort_values("total_pnl", ascending=False)
    return {
        "top1_share": float(ranked.head(1)["total_pnl"].sum() / total),
        "top3_share": float(ranked.head(3)["total_pnl"].sum() / total),
        "top5_share": float(ranked.head(5)["total_pnl"].sum() / total),
    }


def compute_sentiment_lag_correlations(daily_df: pd.DataFrame, max_lag: int = 3) -> pd.DataFrame:
    """Evaluate lagged correlation of sentiment with daily performance.

    Args:
        daily_df: Daily summary dataframe.
        max_lag: Maximum lag in days.

    Returns:
        Dataframe of lagged Spearman correlations.
    """
    df = daily_df.sort_values("date").copy()
    out = []

    for lag in range(1, max_lag + 1):
        temp = df[["date", "sentiment_score", "daily_total_pnl"]].copy()
        temp["lagged_sentiment"] = temp["sentiment_score"].shift(lag)
        temp = temp.dropna(subset=["lagged_sentiment", "daily_total_pnl"])
        if len(temp) < 3:
            rho, p_value = np.nan, np.nan
        else:
            rho, p_value = spearmanr(temp["lagged_sentiment"], temp["daily_total_pnl"])
        out.append({"lag": lag, "spearman_rho": rho, "p_value": p_value})

    return pd.DataFrame(out)


def compute_regime_event_study(daily_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Measure average PnL before and after sentiment regime shifts.

    Args:
        daily_df: Daily summary dataframe.
        window: Days before/after shift to include.

    Returns:
        Event-study dataframe with relative_day and avg_pnl.
    """
    df = daily_df.sort_values("date").copy()
    df["shifted_label"] = df["sentiment_label"].shift(1)
    shifts = df.loc[df["sentiment_label"] != df["shifted_label"], "date"].dropna().tolist()

    records = []
    for shift_day in shifts:
        for rel in range(-window, window + 1):
            target = shift_day + pd.Timedelta(days=rel)
            row = df.loc[df["date"] == target]
            if row.empty:
                continue
            records.append({"relative_day": rel, "daily_total_pnl": row["daily_total_pnl"].iloc[0]})

    if not records:
        return pd.DataFrame(columns=["relative_day", "avg_pnl"])

    out = pd.DataFrame(records).groupby("relative_day", as_index=False).agg(avg_pnl=("daily_total_pnl", "mean"))
    return out


def cluster_traders(trader_features_df: pd.DataFrame, n_clusters: int = 4, seed: int = 42) -> pd.DataFrame:
    """Cluster traders using KMeans on normalized behavior features.

    Args:
        trader_features_df: Trader-level features.
        n_clusters: Number of clusters.
        seed: Random seed.

    Returns:
        Trader features with cluster assignment and cluster label.
    """
    df = trader_features_df.copy()
    use_cols = [
        "win_rate",
        "avg_pnl_per_trade",
        "avg_leverage",
        "long_preference",
        "fear_activity_ratio",
        "greed_activity_ratio",
    ]

    X = df[use_cols].fillna(0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
    df["cluster_id"] = km.fit_predict(X_scaled)

    profile = df.groupby("cluster_id", as_index=False).agg(
        mean_win_rate=("win_rate", "mean"),
        mean_pnl=("avg_pnl_per_trade", "mean"),
        mean_leverage=("avg_leverage", "mean"),
        mean_long_pref=("long_preference", "mean"),
    )

    cluster_names: Dict[int, str] = {}
    for _, row in profile.iterrows():
        cid = int(row["cluster_id"])
        if row["mean_leverage"] > profile["mean_leverage"].median():
            risk = "Aggressive"
        else:
            risk = "Defensive"

        if row["mean_win_rate"] > profile["mean_win_rate"].median():
            consistency = "Consistent"
        else:
            consistency = "Opportunistic"

        cluster_names[cid] = f"{risk} {consistency} Traders"

    df["cluster_label"] = df["cluster_id"].map(cluster_names)
    return df


def smart_money_comparison(merged_df: pd.DataFrame) -> pd.DataFrame:
    """Compare top-decile traders vs others by sentiment regime.

    Args:
        merged_df: Trade-level merged dataframe.

    Returns:
        Comparison dataframe by cohort and sentiment.
    """
    df = merged_df.copy()
    trader_pnl = df.groupby("account", as_index=False).agg(cumulative_pnl=("closedPnL", "sum"))
    threshold = trader_pnl["cumulative_pnl"].quantile(0.90)

    smart_accounts = set(trader_pnl.loc[trader_pnl["cumulative_pnl"] >= threshold, "account"])
    df["cohort"] = np.where(df["account"].isin(smart_accounts), "Smart Money", "Crowd")

    comp = (
        df.groupby(["cohort", "sentiment_label"], as_index=False)
        .agg(
            avg_leverage=("leverage", "mean"),
            long_ratio=("side", lambda s: (s == "LONG").mean()),
            avg_hour=("hour", "mean"),
            avg_pnl=("closedPnL", "mean"),
            trades=("closedPnL", "size"),
        )
    )
    return comp
