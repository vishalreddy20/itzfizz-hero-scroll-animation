"""Data loading utilities for trader sentiment analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


DEFAULT_FEAR_GREED_PATH = Path("data/raw/fear_greed_index.csv")
DEFAULT_TRADES_PATH = Path("data/raw/hyperliquid_trades.csv")


def load_raw_datasets(
    fear_greed_path: Path | str = DEFAULT_FEAR_GREED_PATH,
    trades_path: Path | str = DEFAULT_TRADES_PATH,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw fear-greed and hyperliquid trade datasets.

    Args:
        fear_greed_path: Path to fear-greed CSV file.
        trades_path: Path to hyperliquid trades CSV file.

    Returns:
        Tuple containing (fear_greed_df, trades_df).
    """
    fear_greed_path = Path(fear_greed_path)
    trades_path = Path(trades_path)

    logger.info("Loading fear-greed data from %s", fear_greed_path)
    fear_greed_df = pd.read_csv(fear_greed_path)

    logger.info("Loading trader data from %s", trades_path)
    trades_df = pd.read_csv(trades_path)

    logger.info(
        "Loaded %d fear-greed rows and %d trade rows",
        len(fear_greed_df),
        len(trades_df),
    )
    return fear_greed_df, trades_df
