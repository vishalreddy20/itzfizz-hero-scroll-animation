"""End-to-end pipeline runner for trader sentiment analysis."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.analysis import (
    compute_sentiment_lag_correlations,
    run_kruskal_wallis_pnl_by_sentiment,
    run_spearman_tests,
    run_trade_level_spearman,
    smart_money_top5_vs_rest_by_regime,
    train_profitability_baseline,
    trader_concentration_metrics,
)
from src.data_loader import load_raw_datasets
from src.feature_engineering import build_daily_summary, summarize_by_sentiment
from src.preprocessing import merge_datasets, preprocess_fear_greed, preprocess_trades, save_processed_dataset
from src.visualizations import (
    plot_autocorrelation_sentiment,
    plot_daily_pnl_area,
    plot_lag_correlations,
    plot_leverage_distribution,
    plot_sentiment_distribution,
    plot_sentiment_timeseries,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("pipeline")


def run_pipeline(project_root: Path, mode: str = "full") -> None:
    """Run full project pipeline from loading to outputs.

    Args:
        project_root: Root path of project.
        mode: "full" for complete run, "fast" to skip expensive steps.
    """
    data_raw = project_root / "data" / "raw"
    data_processed = project_root / "data" / "processed"
    fig_dir = project_root / "outputs" / "figures"

    fg_raw, trades_raw = load_raw_datasets(
        fear_greed_path=data_raw / "fear_greed_index.csv",
        trades_path=data_raw / "hyperliquid_trades.csv",
    )

    fg_clean, fg_diag = preprocess_fear_greed(fg_raw)
    trades_clean, quarantine = preprocess_trades(trades_raw)
    merged = merge_datasets(trades_clean, fg_clean)

    save_processed_dataset(merged, data_processed / "merged_dataset.csv")
    quarantine.to_csv(data_processed / "quarantined_records.csv", index=False)
    fg_diag.to_csv(data_processed / "fear_greed_diagnostics.csv", index=False)

    daily = build_daily_summary(merged)
    daily.to_csv(data_processed / "daily_summary.csv", index=False)

    sentiment_summary = summarize_by_sentiment(merged)
    sentiment_summary.to_csv(data_processed / "sentiment_summary.csv", index=False)

    kruskal_out = run_kruskal_wallis_pnl_by_sentiment(merged)
    spearman_out = run_spearman_tests(daily)
    trade_spearman_out = run_trade_level_spearman(merged)
    lag_out = compute_sentiment_lag_correlations(daily, max_lag=3)
    concentration_out = trader_concentration_metrics(merged)
    top5_vs_rest = smart_money_top5_vs_rest_by_regime(merged)
    model_out = {
        "train_rows": float("nan"),
        "test_rows": float("nan"),
        "accuracy": float("nan"),
        "f1": float("nan"),
        "roc_auc": float("nan"),
    }
    if mode == "full":
        model_out = train_profitability_baseline(merged)

    trade_spearman_out.to_csv(data_processed / "trade_level_spearman.csv", index=False)
    top5_vs_rest.to_csv(data_processed / "top5_vs_rest_regime_summary.csv", index=False)
    pd.DataFrame([model_out]).to_csv(data_processed / "profitability_baseline_metrics.csv", index=False)

    zero_pnl_pct = (merged["closedPnL"] == 0).mean() * 100
    leverage_q = merged["leverage"].quantile([0.25, 0.5, 0.75, 0.95, 0.99]).to_dict()

    if mode == "full":
        plot_sentiment_timeseries(fg_clean, fig_dir / "sentiment_timeseries.png")
        plot_sentiment_distribution(fg_clean, fig_dir / "sentiment_distribution.png")
        plot_autocorrelation_sentiment(fg_clean, fig_dir / "sentiment_autocorrelation.png")
        plot_daily_pnl_area(daily, fig_dir / "daily_pnl_area.png")
        plot_leverage_distribution(merged, fig_dir / "leverage_distribution.png")
        plot_lag_correlations(lag_out, fig_dir / "lag_correlations.png")
    else:
        logger.info("FAST mode enabled: skipped figure generation and baseline model training.")

    logger.info("========== KEY STATS ==========")
    logger.info("Merged rows: %d", len(merged))
    logger.info("Date span: %s to %s", merged["date"].min(), merged["date"].max())
    logger.info("Average trade PnL: %.4f", merged["closedPnL"].mean())
    logger.info("Overall win rate: %.2f%%", merged["is_profitable"].mean() * 100)
    logger.info("Zero closedPnL share: %.2f%%", zero_pnl_pct)
    logger.info(
        "Leverage quantiles p25=%.2f p50=%.2f p75=%.2f p95=%.2f p99=%.2f",
        leverage_q.get(0.25, float("nan")),
        leverage_q.get(0.5, float("nan")),
        leverage_q.get(0.75, float("nan")),
        leverage_q.get(0.95, float("nan")),
        leverage_q.get(0.99, float("nan")),
    )
    logger.info(
        "Kruskal-Wallis H=%.4f p=%.4g epsilon_squared=%.6f",
        kruskal_out["statistic"],
        kruskal_out["p_value"],
        kruskal_out["epsilon_squared"],
    )
    logger.info(
        "Trader concentration top1=%.2f%% top3=%.2f%% top5=%.2f%%",
        concentration_out["top1_share"] * 100,
        concentration_out["top3_share"] * 100,
        concentration_out["top5_share"] * 100,
    )
    logger.info(
        "Baseline model OOS metrics accuracy=%.4f f1=%.4f roc_auc=%.4f (train=%s test=%s)",
        model_out["accuracy"],
        model_out["f1"],
        model_out["roc_auc"],
        "NA" if pd.isna(model_out["train_rows"]) else str(int(model_out["train_rows"])),
        "NA" if pd.isna(model_out["test_rows"]) else str(int(model_out["test_rows"])),
    )

    with pd.option_context("display.max_rows", 50, "display.max_columns", 20):
        logger.info("\nSpearman tests:\n%s", spearman_out.to_string(index=False))
        logger.info("\nTrade-level Spearman tests:\n%s", trade_spearman_out.to_string(index=False))
        logger.info("\nLagged correlations:\n%s", lag_out.to_string(index=False))
        logger.info("\nSentiment summary:\n%s", sentiment_summary.to_string(index=False))
        logger.info("\nTop5 vs Other27 by regime:\n%s", top5_vs_rest.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run trader sentiment pipeline.")
    parser.add_argument(
        "--mode",
        choices=["full", "fast"],
        default="full",
        help="Execution mode: full (all outputs) or fast (skip heavy steps).",
    )
    args = parser.parse_args()
    run_pipeline(Path(__file__).resolve().parent, mode=args.mode)
