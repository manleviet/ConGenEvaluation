# busybox rs_1n example-first, cap 5,000 — one fold

**One fold, not a three-fold cell.** It stands as a cap-sensitivity point beside the
other cap probes; it is not a row of the gap table, where every cell is a mean over
three folds. The filename deliberately omits `_cv_` so the scoring and table tools,
which glob `*_cv_*.json`, do not pick it up as a cell.

Fold 0 only, same split and seed as the cap-1,000 run (`n_folds = 3`, `--folds 0`), so
it compares against that run's fold 0 and nothing else.

| | cap 1,000 | cap 5,000 |
|---|---|---|
| queries | 1,000 | 5,000 |
| stop | `max_queries` | `max_queries` |
| \|KB\| | 14 | **14 — the identical set** |
| wall clock | 2.12 h | **15.53 h** |
| consistency checks | 1,014 | 5,014 |
| seconds per query | 7.6 | 11.2 |

Five times the budget bought no constraint at all — not a different theory of the same
size, the same fourteen constraints — while costing 7.32x the time. Over the same
1,000 -> 5,000 range the smaller models gain: fqa x1.44, REAL-FM-4 x1.37, arcade x1.34.

`timeout_s` was raised to 16 h for this run because the sweep's 6 h guard would have
fired and stamped `convergence_reason='timeout'`, which the config's own comment says
makes a fold incomparable. It finished on `max_queries` with 28 minutes to spare.
