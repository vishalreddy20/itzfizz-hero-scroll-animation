# Final Insights Report: Bitcoin Sentiment vs Trader Performance

## Section 1: Executive Summary

- Trader performance differs materially across sentiment regimes (Kruskal-Wallis $H=1226.9956$, $p=2.238\times10^{-264}$).
- Risk exposure (leverage and position size) changes between fear and greed states, indicating regime-dependent risk appetite.
- Directional bias shifts across extreme sentiment states, revealing crowd trend-following or contrarian behavior.
- Daily win rate improves as sentiment score rises (Spearman $\rho=0.1610$, $p=0.000404$).
- Daily average leverage declines as sentiment score rises (Spearman $\rho=-0.1124$, $p=0.0138$).
- Top-decile cumulative PnL traders ("Smart Money") display behavior distinct from the broader crowd in regime transitions.

## Section 2: Sentiment-Performance Relationship

- By mean PnL per trade, Extreme Greed is highest (67.8929), while Extreme Fear is lower (34.5379).
- By win rate, Extreme Greed is highest (0.4649), while Extreme Fear is lowest (0.3706).
- These differences are statistically significant across sentiment groups (Kruskal-Wallis $p\ll0.001$).
- Practical interpretation: traders perform better in greed regimes than fear regimes on this dataset, and strategy/risk settings should be regime-aware.

## Section 3: Behavioral Patterns

- Leverage and position-size distributions differ by regime, showing dynamic risk scaling.
- Long/short participation shifts in extreme fear vs extreme greed, indicating directional crowd response.
- Smart Money appears less reactive and potentially more selective than the crowd during high-emotion periods.

## Section 4: Lag & Predictability

- Lag analysis evaluates whether sentiment $t-1$, $t-2$, and $t-3$ predicts day-$t$ performance.
- Optimal lag is selected by highest absolute Spearman correlation and lowest statistically meaningful p-value.
- Findings suggest short lag windows can provide tactical context for risk-on/risk-off adjustments.

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

- Data limitations: Trade export may omit explicit leverage for some records; fallback proxies are used when needed.
- Data limitations: Closed PnL values at trade granularity may include many zero/open records, affecting distribution shape.
- Data limitations: Sentiment is daily and broad-market; it may miss intraday regime changes.
- Additional data: Funding rates, open interest, liquidation data, realized volatility, and BTC returns.
- Additional data: Trader-level metadata such as strategy type, holding duration, and stop-loss behavior.
- ML extensions: Sentiment-regime classifier for expected risk state.
- ML extensions: Regime-conditioned PnL forecasting model.
- ML extensions: Meta-labeling model for trade-quality filtering.
