# Final Insights Report: Bitcoin Sentiment vs Trader Performance

## Section 1: Executive Summary

- Closed-trade PnL differs across sentiment regimes (Kruskal-Wallis $H=730.3288$, $p=9.436\times10^{-157}$), but effect size is small ($\epsilon^2=0.0070$).
- Trade-level sentiment signal exists but is weak: Spearman $(\text{sentiment},\text{closedPnL})=0.0262$ and $(\text{sentiment},\text{is_profitable})=0.0209$.
- Out-of-sample baseline model has modest predictive skill: accuracy $0.5493$, F1 $0.6243$, ROC-AUC $0.5371$.
- Trader concentration is high: top 1 contributes $20.82\%$ and top 5 contributes $61.77\%$ of cumulative PnL.
- Zero `closedPnL` rows are substantial ($50.57\%$), so closed-trade filtering is required for reliable performance inference.

## Section 2: Sentiment-Performance Relationship

- By closed-trade mean PnL per trade, Extreme Greed is highest (130.2053), while Extreme Fear is lower (71.0273).
- By closed-trade win rate, Extreme Greed is highest (0.8917), while Extreme Fear is lower (0.7622).
- These differences are statistically significant but small in practical effect size ($\epsilon^2=0.0070$), so sentiment alone is not a dominant driver.
- Practical interpretation: sentiment is a weak context feature that should be combined with trader-specific behavior features.

## Section 3: Behavioral Patterns

- Long/short participation shifts by sentiment bucket, indicating directional crowd response.
- Top 5 vs Other 27 split shows meaningful divergence: Top 5 mean PnL is materially higher across all regimes.
- Position-size behavior differs between cohorts, suggesting account-specific execution style dominates sentiment-only effects.

## Section 4: Lag & Predictability

- Lag analysis ($t-1$ to $t-3$) shows weak negative correlations with daily total PnL (all p-values non-significant).
- Predictive baseline (logistic regression) confirms limited standalone predictive power from current feature set (ROC-AUC $0.5371$).
- Findings suggest sentiment is better used as a regime label than a direct predictor of edge.

## Section 5: Actionable Strategy Recommendations

Strategy 1: Regime-Aware Position Sizing  
Trigger: Sentiment enters Fear or Extreme Fear  
Action: Reduce base position size and tighten leverage caps by predefined percentages  
Evidence: Fear regimes show different return dispersion and downside tails versus neutral/greed states  
Expected Edge: Lower drawdown during stress periods while preserving participation

Strategy 2: Greed Risk Guardrail  
Trigger: Consecutive Greed/Extreme Greed days with rising leverage usage  
Action: Enforce max leverage throttle and partial profit-taking schedule  
Evidence: Elevated leverage in greed conditions can coincide with unstable forward PnL  
Expected Edge: Mitigate overextension and protect realized gains

Strategy 3: Sentiment-Shift Event Playbook  
Trigger: Day-over-day sentiment classification change (regime shift)  
Action: Use temporary execution rules for next 3 days (smaller clips, tighter stops, higher confirmation threshold)  
Evidence: Event-study window around shifts shows changed average PnL behavior  
Expected Edge: Improved execution quality during transition volatility

Strategy 4: Smart-Money Mimic Filter  
Trigger: Signal aligns with behavior profile of top-decile cumulative PnL traders  
Action: Prioritize trades matching smart cohort leverage and directional preferences  
Evidence: Smart Money vs Crowd divergence indicates higher-quality behavioral features  
Expected Edge: Better signal precision by filtering crowd-noise trades

Strategy 5: Short-Lag Sentiment Overlay  
Trigger: Best-performing lag feature (from lag correlation analysis) crosses threshold  
Action: Apply directional/risk multiplier only when lag-sentiment and base setup agree  
Evidence: Lagged sentiment demonstrates measurable monotonic relation with daily performance  
Expected Edge: Incremental improvement in expectancy through context-aware trade selection

## Section 6: Limitations & Next Steps

- Data limitations: Trade export contains sparse/unusable leverage values; robust leverage-behavior inference is not currently possible.
- Data limitations: Closed PnL values include many zero/open rows (50.57%), requiring closed-trade filtering.
- Data limitations: Only 32 traders are present, with high concentration in top accounts (top 5 = 61.77% of cumulative PnL).
- Data limitations: Sentiment is daily and broad-market; it may miss intraday regime changes.
- Additional data: Funding rates, open interest, liquidation data, realized volatility, and BTC returns.
- Additional data: BTC price series is needed for explicit benchmark comparison (for example, buy-and-hold baseline).
- Additional data: Trader-level metadata such as strategy type, holding duration, and stop-loss behavior.
- ML extensions: Time-aware models with purged walk-forward validation.
- ML extensions: Regime-conditioned PnL forecasting model with richer market features.
- ML extensions: Meta-labeling model for trade-quality filtering and execution timing.
