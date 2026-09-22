# Example Generation Summary

Generated examples for constraint acquisition evaluation (AcqMSS paper).

## Sampling Strategies

| Strategy | Description                                       |
|----------|---------------------------------------------------|
| `rs_1n`  | Random Sampling with n examples                   |
| `rs_2n`  | Random Sampling with 2n examples                  |
| `rs_3n`  | Random Sampling with 3n examples                  |
| `rs_m`   | Random Sampling with m examples (m = 2-COV count) |
| `2cov`   | 2-wise Coverage (pairwise)                        |
| `ff`     | Feature Frequency — runs until every attainable (feature, value) pair is covered; 10n is a safety cap, not the operating point |

## Feature Models and Example Counts

| Model          |     n | #valid |     2^n | rs_1n |  rs_2n |  rs_3n | rs_m | 2cov |    ff |
|----------------|------:|-------:|--------:|------:|-------:|-------:|-----:|-----:|------:|
| REAL-FM-7      |    14 |     80 |  16,384 |    14 |     28 |     42 |    9 |    9 |     9 |
| arcade-game    |    65 |    TBD |   2^65  |    65 |    130 |    195 |   14 |   14 |    30 |
| fqa            |   179 |    TBD |   2^179 |   179 |    358 |    537 |   16 |   16 |    70 |
| REAL-FM-4      |   291 |    TBD |   2^291 |   291 |    582 |    873 |   18 |   18 |   113 |
| busybox-1.18.0 |   854 |    TBD |   2^854 |   854 |  1,708 |  2,562 |   21 |   21 |   401 |
| ea2468         | 1,408 |    TBD |  2^1408 | 1,408 |  2,816 |  4,224 |   22 |   22 |   345 |

**Notes:**
- `n` = number of features in the model
- `#valid` = number of valid configurations (solutions satisfying all constraints)
- `2^n` = total configuration space (all possible combinations)
- `m` = smallest number of valid configurations for 2-wise coverage
- `rs_m` and `2cov` have the same count (m examples)
- For complex FMs, most random configurations are invalid (E-)
- TBD = To Be Determined (computation takes too long for large models)
- `ff` counts are measured, not capped: FF stops on attainable coverage, so it
  lands far below 10n (busybox uses 392 of its 8,540 cap). A pair is attainable
  when some valid configuration exhibits it — mandatory features can never be
  False in a positive example, so those pairs are excluded from the target rather
  than chased forever.

### Not evaluated

`linux-2.6.33.3` (n = 6,467) is in the repository — UVL, bias config and bias
stats — because B3 needs its |B|. It is **not** an evaluated knowledge base: it
was dropped from the paper on 2026-08-21 and no example sets or folds are
generated for it. Keep the files; do not add it to the table above.

## Usage

```bash
python -m apps.generate_examples apps/conf/generate_examples_config.toml
```
