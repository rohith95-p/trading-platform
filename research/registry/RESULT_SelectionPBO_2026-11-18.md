# Selection stability of the 16 recovered strategies

The strategy with the best training Sharpe ranked in the lower half on the complementary dates in 144 of 252 splits (57.14%). Its average return was negative on the complementary dates in 190 of 252 splits (75.40%). All splits had defined Sharpe scores. The median out-of-sample rank logit was −0.118.

The frozen panel covers realized daily returns for 16 previously studied strategies. Ten blocks of 104 observations cover January 3, 2022 through December 26, 2025. Three tail observations were excluded under the registered equal-block rule. Complementary splits share observations. These percentages describe selection instability within the recovered panel. Individual split outcomes cannot be treated as independent trials, and the historical search contained additional candidates. Daily closing cash can miss open-position risk. The result provides no estimate of Atlas payout eligibility.

Protocol commit 5f76b36. Reproduce with `python -m scripts.research.selection_pbo`. See `research/results/finalization_2026-11-18/selection_pbo.json` for every split, input identity and candidate ordering. Method from [Bailey, Borwein, López de Prado and Zhu](https://escholarship.org/uc/item/4w1110bb).
