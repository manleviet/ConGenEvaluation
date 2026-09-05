# Evaluation Results

Generated from: data/results_sosym_r1

KB Mapping: KB1=REAL-FM-7, KB2=fqa, KB3=arcade-game, KB4=REAL-FM-4, KB5=busybox-1.18.0

Cell markers: `n/a` = this (knowledge base, sampling) combination was not run; `-` = the run exists but this strategy tier was not scored. Neither is a measured zero.


# Paper Tables (Incremental)

## Table 7: AcqMSS #consistency checks and runtime (msec) - Incremental Mode

| Strategy | |E+| | |E-| | KB1 | KB2 | KB3 | KB4 | KB5 |
|:---|---:|---:|:---:|:---:|:---:|:---:|:---:|
| RS(1n) | 8 | 0 | 515 / 194.3 | 706 / 5187.9 | 3090 / 16171.7 | 3591 / 186496.3 | 11107 / 15142442.8 |
| RS(2n) | 17 | 1 | 538 / 394.3 | 713 / 16508.8 | 3241 / 36643.8 | 3751 / 668106.7 | n/a |
| RS(3n) | 25 | 2 | 544 / 623.5 | 744 / 34085.5 | 3290 / 55001.2 | 3786 / 1550234.0 | n/a |
| RS(m) | 5 | 0 | 466 / 124.7 | 476 / 239.1 | 2187 / 2105.7 | 2526 / 4754.8 | 7742 / 44203.7 |
| 2-COV | 0 | 6 | 10 / 75.1 | 10 / 715.0 | 1429 / 922.4 | 1612 / 1823.4 | 14 / 7446.7 |
| FF | 4 | 2 | 464 / 124.8 | 641 / 1423.3 | 2702 / 4236.4 | 3427 / 41809.8 | 9691 / 2938078.6 |

## Table 9: Accuracy with Random Sampling (RS) - Incremental Mode

| Strategy | KB1 | KB2 | KB3 | KB4 | KB5 |
|:---|:---:|:---:|:---:|:---:|:---:|
| RS(1n) | 0.2778 ± 0.0481 | 0.8543 ± 0.0693 | 0.4149 ± 0.0371 | 0.8243 ± 0.0742 | 0.8665 ± 0.0287 |
| RS(2n) | 0.5583 ± 0.2184 | 0.9271 ± 0.0430 | 0.5086 ± 0.1336 | 0.8934 ± 0.0419 | n/a |
| RS(3n) | 0.8603 ± 0.1430 | 0.9665 ± 0.0057 | 0.5542 ± 0.0657 | 0.9244 ± 0.0225 | n/a |
| RS(m) | 0.1944 ± 0.1735 | 0.3667 ± 0.1528 | 0.1944 ± 0.1735 | 0.2175 ± 0.0614 | 0.0893 ± 0.0778 |

## Table 10: Accuracy with 2-COV - Incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | 1.0000 ± 0.0000 |
| KB2 | 1.0000 ± 0.0000 |
| KB3 | 0.9444 ± 0.0962 |
| KB4 | 0.9524 ± 0.0825 |
| KB5 | 1.0000 ± 0.0000 |

## Table 11: Accuracy with FF - Incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | 0.3333 ± 0.0000 |
| KB2 | 0.8134 ± 0.0688 |
| KB3 | 0.3189 ± 0.2178 |
| KB4 | 0.7159 ± 0.0615 |
| KB5 | 0.7057 ± 0.0485 |

# Additional Tables (Incremental)

## Table: Fold Metrics (Precision / Recall / F1) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 1.00/0.23/0.38 | 1.00/0.53/0.68 | 1.00/0.85/0.91 | 0.33/0.11/0.17 | 0.00/0.00/0.00 | 0.00/0.00/0.00 |
| KB2 | 1.00/0.84/0.91 | 1.00/0.92/0.96 | 1.00/0.96/0.98 | 1.00/0.33/0.49 | 0.00/0.00/0.00 | 1.00/0.79/0.88 |
| KB3 | 1.00/0.36/0.52 | 1.00/0.45/0.61 | 1.00/0.51/0.67 | 0.67/0.15/0.24 | 0.00/0.00/0.00 | 0.67/0.19/0.28 |
| KB4 | 1.00/0.81/0.89 | 1.00/0.88/0.94 | 1.00/0.92/0.96 | 1.00/0.18/0.30 | 0.00/0.00/0.00 | 1.00/0.70/0.82 |
| KB5 | 1.00/0.85/0.92 | n/a | n/a | 0.00/0.00/0.00 | 0.00/0.00/0.00 | 1.00/0.70/0.82 |

## Table: Accuracy (Compact) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.28±0.05 | 0.56±0.22 | 0.86±0.14 | 0.19±0.17 | 1.00±0.00 | 0.33±0.00 |
| KB2 | 0.85±0.07 | 0.93±0.04 | 0.97±0.01 | 0.37±0.15 | 1.00±0.00 | 0.81±0.07 |
| KB3 | 0.41±0.04 | 0.51±0.13 | 0.55±0.07 | 0.19±0.17 | 0.94±0.10 | 0.32±0.22 |
| KB4 | 0.82±0.07 | 0.89±0.04 | 0.92±0.02 | 0.22±0.06 | 0.95±0.08 | 0.72±0.06 |
| KB5 | 0.87±0.03 | n/a | n/a | 0.09±0.08 | 1.00±0.00 | 0.71±0.05 |

## Table: Accuracy by Sampling Strategy - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.2778 ± 0.0481 | 0.5583 ± 0.2184 | 0.8603 ± 0.1430 | 0.1944 ± 0.1735 | 1.0000 ± 0.0000 | 0.3333 ± 0.0000 |
| KB2 | 0.8543 ± 0.0693 | 0.9271 ± 0.0430 | 0.9665 ± 0.0057 | 0.3667 ± 0.1528 | 1.0000 ± 0.0000 | 0.8134 ± 0.0688 |
| KB3 | 0.4149 ± 0.0371 | 0.5086 ± 0.1336 | 0.5542 ± 0.0657 | 0.1944 ± 0.1735 | 0.9444 ± 0.0962 | 0.3189 ± 0.2178 |
| KB4 | 0.8243 ± 0.0742 | 0.8934 ± 0.0419 | 0.9244 ± 0.0225 | 0.2175 ± 0.0614 | 0.9524 ± 0.0825 | 0.7159 ± 0.0615 |
| KB5 | 0.8665 ± 0.0287 | n/a | n/a | 0.0893 ± 0.0778 | 1.0000 ± 0.0000 | 0.7057 ± 0.0485 |

## Table: Runtime, mean [min–max over folds] - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | 194 [183–202] | 394 [375–424] | 623 [604–658] | 125 [112–143] | 75 [65–94] | 125 [111–147] |
| KB2 | 5.19s [4.99s–5.47s] | 16.51s [16.24s–17.05s] | 34.09s [32.99s–35.70s] | 239 [201–269] | 715 [648–807] | 1.42s [1.39s–1.46s] |
| KB3 | 16.17s [15.23s–16.81s] | 36.64s [31.29s–39.48s] | 55.00s [53.67s–56.72s] | 2.11s [1.93s–2.25s] | 922 [720–1.04s] | 4.24s [4.19s–4.26s] |
| KB4 | 186.50s [182.98s–189.11s] | 668.11s [655.72s–682.33s] | 1550.23s [1490.90s–1619.18s] | 4.75s [4.50s–5.02s] | 1.82s [1.39s–2.12s] | 41.81s [40.55s–42.45s] |
| KB5 | 15142.44s [14769.29s–15620.12s] | n/a | n/a | 44.20s [40.52s–46.36s] | 7.45s [7.04s–7.87s] | 2938.08s [2760.87s–3066.91s] |

## Table: Consistency Checks - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | 515 | 538 | 544 | 466 | 10 | 464 |
| KB2 | 706 | 713 | 744 | 476 | 10 | 641 |
| KB3 | 3090 | 3241 | 3290 | 2187 | 1429 | 2702 |
| KB4 | 3591 | 3751 | 3786 | 2526 | 1612 | 3427 |
| KB5 | 11107 | n/a | n/a | 7742 | 14 | 9691 |

## Table: Performance Metrics (Incremental)

| KB | Strategy | Runtime (ms) | #Checks | Memory (MB) | n_bias | n_mss | n_kb |
|:---|:---|---:|---:|---:|---:|---:|---:|
| KB1 | RS(1n) | 194.30 ± 9.92 | 515 ± 10 | 0.35 | 295 | 91.7 | 18.3 |
| KB1 | RS(2n) | 394.31 ± 25.81 | 538 ± 6 | 0.50 | 295 | 69.0 | 18.7 |
| KB1 | RS(3n) | 623.50 ± 29.71 | 544 ± 7 | 0.63 | 295 | 61.7 | 13.7 |
| KB1 | RS(m) | 124.74 ± 15.94 | 466 ± 9 | 0.32 | 295 | 131.7 | 18.7 |
| KB1 | 2-COV | 75.11 ± 16.28 | 10 ± 0 | 0.34 | 295 | 294.0 | 9.7 |
| KB1 | FF | 124.84 ± 19.39 | 464 ± 31 | 0.35 | 295 | 133.3 | 17.0 |
| KB2 | RS(1n) | 5187.85 ± 248.75 | 706 ± 19 | 8.24 | 459 | 224.7 | 130.7 |
| KB2 | RS(2n) | 16508.77 ± 470.56 | 713 ± 22 | 15.32 | 459 | 216.0 | 135.0 |
| KB2 | RS(3n) | 34085.51 ± 1431.44 | 744 ± 5 | 22.38 | 459 | 201.3 | 136.0 |
| KB2 | RS(m) | 239.13 ± 34.86 | 476 ± 29 | 1.60 | 459 | 344.3 | 108.3 |
| KB2 | 2-COV | 715.03 ± 82.63 | 10 ± 0 | 1.35 | 459 | 458.0 | 104.3 |
| KB2 | FF | 1423.34 ± 32.02 | 641 ± 10 | 3.90 | 459 | 269.3 | 120.7 |
| KB3 | RS(1n) | 16171.69 ± 831.43 | 3090 ± 21 | 4.07 | 1755 | 540.7 | 177.7 |
| KB3 | RS(2n) | 36643.77 ± 4637.61 | 3241 ± 24 | 6.85 | 1755 | 371.3 | 244.0 |
| KB3 | RS(3n) | 55001.19 ± 1559.45 | 3290 ± 10 | 9.87 | 1755 | 313.7 | 225.3 |
| KB3 | RS(m) | 2105.70 ± 160.75 | 2187 ± 95 | 2.12 | 1755 | 1167.0 | 75.0 |
| KB3 | 2-COV | 922.37 ± 175.79 | 1429 ± 1227 | 2.08 | 1755 | 1374.7 | 48.7 |
| KB3 | FF | 4236.42 ± 43.23 | 2702 ± 88 | 2.50 | 1755 | 852.7 | 102.7 |
| KB4 | RS(1n) | 186496.28 ± 3159.81 | 3591 ± 101 | 23.81 | 2079 | 715.3 | 243.7 |
| KB4 | RS(2n) | 668106.67 ± 13400.43 | 3751 ± 25 | 45.84 | 2079 | 565.0 | 249.7 |
| KB4 | RS(3n) | 1550234.04 ± 64675.39 | 3786 ± 40 | 68.04 | 2079 | 509.0 | 238.0 |
| KB4 | RS(m) | 4754.85 ± 260.77 | 2526 ± 68 | 4.28 | 2079 | 1421.0 | 222.0 |
| KB4 | 2-COV | 1823.38 ± 383.20 | 1612 ± 1385 | 3.35 | 2079 | 1678.7 | 139.0 |
| KB4 | FF | 41809.77 ± 1090.09 | 3427 ± 114 | 10.82 | 2079 | 869.0 | 231.3 |
| KB5 | RS(1n) | 15142442.79 ± 434940.74 | 11107 ± 40 | 194.55 | 6635 | 2542.7 | 688.0 |
| KB5 | RS(m) | 44203.69 ± 3204.56 | 7742 ± 454 | 12.86 | 6635 | 4637.3 | 485.7 |
| KB5 | 2-COV | 7446.65 ± 411.19 | 14 ± 0 | 9.62 | 6635 | 6634.0 | 7.7 |
| KB5 | FF | 2938078.64 ± 158654.54 | 9691 ± 489 | 95.26 | 6635 | 3576.0 | 648.3 |

## Table: KB Summary (Incremental)

| KB | Strategy | n_bias | n_kb (mean) | n_intersected | Reduction |
|:---|:---|---:|---:|---:|---:|
| KB1 | RS(1n) | 295 | 18.3 | 1 | 93.8% |
| KB1 | RS(2n) | 295 | 18.7 | 3 | 93.7% |
| KB1 | RS(3n) | 295 | 13.7 | 1 | 95.4% |
| KB1 | RS(m) | 295 | 18.7 | 0 | 93.7% |
| KB1 | 2-COV | 295 | 9.7 | 0 | 96.7% |
| KB1 | FF | 295 | 17.0 | 0 | 94.2% |
| KB2 | RS(1n) | 459 | 130.7 | 104 | 71.5% |
| KB2 | RS(2n) | 459 | 135.0 | 113 | 70.6% |
| KB2 | RS(3n) | 459 | 136.0 | 124 | 70.4% |
| KB2 | RS(m) | 459 | 108.3 | 80 | 76.4% |
| KB2 | 2-COV | 459 | 104.3 | 41 | 77.3% |
| KB2 | FF | 459 | 120.7 | 92 | 73.7% |
| KB3 | RS(1n) | 1755 | 177.7 | 51 | 89.9% |
| KB3 | RS(2n) | 1755 | 244.0 | 132 | 86.1% |
| KB3 | RS(3n) | 1755 | 225.3 | 133 | 87.2% |
| KB3 | RS(m) | 1755 | 75.0 | 26 | 95.7% |
| KB3 | 2-COV | 1755 | 48.7 | 2 | 97.2% |
| KB3 | FF | 1755 | 102.7 | 28 | 94.2% |
| KB4 | RS(1n) | 2079 | 243.7 | 171 | 88.3% |
| KB4 | RS(2n) | 2079 | 249.7 | 184 | 88.0% |
| KB4 | RS(3n) | 2079 | 238.0 | 180 | 88.6% |
| KB4 | RS(m) | 2079 | 222.0 | 139 | 89.3% |
| KB4 | 2-COV | 2079 | 139.0 | 0 | 93.3% |
| KB4 | FF | 2079 | 231.3 | 156 | 88.9% |
| KB5 | RS(1n) | 6635 | 688.0 | 568 | 89.6% |
| KB5 | RS(m) | 6635 | 485.7 | 304 | 92.7% |
| KB5 | 2-COV | 6635 | 7.7 | 0 | 99.9% |
| KB5 | FF | 6635 | 648.3 | 389 | 90.2% |

# Strategy Evaluation (Incremental)

### ConGen
## Table: Three-tier F1 on Intersected KB (Desc / Clause / Sem) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.30/0.71/0.87 | 0.40/0.77/0.90 | 0.38/0.77/0.96 | 0.19/0.52/0.78 | 0.00/0.13/0.85 | 0.23/0.60/0.85 |
| KB2 | 0.78/0.94/0.95 | 0.76/0.94/0.94 | 0.78/0.95/0.95 | 0.76/0.93/0.94 | 0.41/0.76/0.87 | 0.74/0.91/0.92 |
| KB3 | 0.31/0.55/0.66 | 0.28/0.49/0.58 | 0.26/0.48/0.60 | 0.44/0.65/0.81 | 0.28/0.48/0.70 | 0.38/0.59/0.73 |
| KB4 | 0.63/0.77/0.82 | 0.67/0.82/0.88 | 0.69/0.83/0.90 | 0.58/0.75/0.80 | 0.32/0.54/0.93 | 0.57/0.75/0.81 |
| KB5 | 0.51/0.59/0.89 | n/a | n/a | 0.38/0.58/0.91 | 0.00/0.01/1.00 | 0.47/0.58/0.89 |

### ConGen
## Table: Semantic tier on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 1.00/0.78/0.87 | 1.00/0.82/0.90 | 0.98/0.93/0.96 | 0.89/0.68/0.78 | 0.94/0.77/0.85 | 1.00/0.74/0.85 |
| KB2 | 1.00/0.90/0.95 | 1.00/0.88/0.94 | 1.00/0.91/0.95 | 1.00/0.88/0.94 | 1.00/0.77/0.87 | 1.00/0.85/0.92 |
| KB3 | 0.97/0.50/0.66 | 0.98/0.41/0.58 | 0.97/0.43/0.60 | 1.00/0.68/0.81 | 0.75/0.77/0.70 | 0.98/0.58/0.73 |
| KB4 | 0.97/0.70/0.82 | 1.00/0.78/0.88 | 1.00/0.81/0.90 | 1.00/0.67/0.80 | 1.00/0.87/0.93 | 1.00/0.68/0.81 |
| KB5 | 1.00/0.81/0.89 | n/a | n/a | 1.00/0.83/0.91 | 1.00/0.99/1.00 | 1.00/0.80/0.89 |

### ConGen
## Table: Exact equivalence of the delivered theory (folds attaining / scored); `--` = not measured, `0/n` = measured and none attained - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0/3 | 0/3 | 1/3 | 0/3 | 0/3 | 0/3 |
| KB2 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB4 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB5 | 0/3 | n/a | n/a | 0/3 | 0/3 | 0/3 |

### QuAcq (example-only)
## Table: Three-tier F1 on Intersected KB (Desc / Clause / Sem) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.10/0.14/0.46 | 0.00/0.09/0.43 | 0.00/0.09/0.43 | 0.00/0.09/0.43 | 0.10/0.14/0.46 | 0.09/0.19/0.50 |
| KB2 | 0.03/0.03/0.05 | 0.06/0.04/0.06 | 0.05/0.04/0.06 | 0.00/0.01/0.03 | 0.02/0.02/0.05 | 0.04/0.02/0.05 |
| KB3 | 0.04/0.04/0.06 | 0.05/0.04/0.07 | 0.07/0.06/0.13 | 0.02/0.03/0.05 | 0.08/0.08/0.15 | 0.03/0.03/0.06 |
| KB4 | 0.03/0.03/0.04 | 0.03/0.03/0.04 | 0.03/0.03/0.04 | 0.00/0.00/0.01 | 0.01/0.01/0.04 | 0.01/0.01/0.02 |
| KB5 | 0.02/0.02/0.63 | n/a | n/a | 0.00/0.00/0.62 | 0.00/0.00/0.62 | 0.00/0.01/0.62 |

### QuAcq (example-only)
## Table: Semantic tier on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.30/1.00/0.46 | 0.27/1.00/0.43 | 0.27/1.00/0.43 | 0.27/1.00/0.43 | 0.30/1.00/0.46 | 0.33/1.00/0.50 |
| KB2 | 0.03/1.00/0.05 | 0.03/1.00/0.06 | 0.03/1.00/0.06 | 0.02/1.00/0.03 | 0.03/1.00/0.05 | 0.03/1.00/0.05 |
| KB3 | 0.03/1.00/0.06 | 0.04/1.00/0.07 | 0.07/1.00/0.13 | 0.03/1.00/0.05 | 0.08/1.00/0.15 | 0.03/1.00/0.06 |
| KB4 | 0.02/1.00/0.04 | 0.02/1.00/0.04 | 0.02/1.00/0.04 | 0.01/1.00/0.01 | 0.02/1.00/0.04 | 0.01/1.00/0.02 |
| KB5 | 0.46/1.00/0.63 | n/a | n/a | 0.45/1.00/0.62 | 0.45/1.00/0.62 | 0.45/1.00/0.62 |

### QuAcq (example-only)
## Table: Exact equivalence of the delivered theory (folds attaining / scored); `--` = not measured, `0/n` = measured and none attained - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB2 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB4 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB5 | 0/3 | n/a | n/a | 0/3 | 0/3 | 0/3 |

### QuAcq (example-first)
## Table: Three-tier F1 on Intersected KB (Desc / Clause / Sem) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.33/0.43/0.67 | 0.17/0.28/0.56 | 0.33/0.43/0.67 | 0.16/0.30/0.57 | 0.37/0.45/0.68 | 0.29/0.39/0.64 |
| KB2 | 0.25/0.18/0.20 | 0.26/0.18/0.20 | 0.22/0.15/0.18 | 0.22/0.17/0.19 | 0.16/0.12/0.14 | 0.25/0.17/0.20 |
| KB3 | 0.56/0.53/0.63 | 0.50/0.46/0.56 | 0.68/0.66/0.75 | 0.49/0.44/0.52 | 0.38/0.35/0.44 | 0.44/0.44/0.56 |
| KB4 | 0.10/0.10/0.11 | 0.25/0.24/0.25 | 0.08/0.08/0.09 | 0.09/0.08/0.09 | 0.04/0.05/0.08 | 0.21/0.20/0.21 |
| KB5 | 0.03/0.03/0.63 | n/a | n/a | 0.00/0.01/0.62 | 0.01/0.02/0.63 | 0.01/0.03/0.63 |

### QuAcq (example-first)
## Table: Semantic tier on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.50/1.00/0.67 | 0.39/1.00/0.56 | 0.50/1.00/0.67 | 0.41/1.00/0.57 | 0.52/1.00/0.68 | 0.47/1.00/0.64 |
| KB2 | 0.11/1.00/0.20 | 0.12/1.00/0.20 | 0.10/1.00/0.18 | 0.11/1.00/0.19 | 0.08/1.00/0.14 | 0.11/1.00/0.20 |
| KB3 | 0.47/1.00/0.63 | 0.40/1.00/0.56 | 0.60/1.00/0.75 | 0.35/1.00/0.52 | 0.30/1.00/0.44 | 0.40/1.00/0.56 |
| KB4 | 0.06/1.00/0.11 | 0.15/0.99/0.25 | 0.05/1.00/0.09 | 0.05/1.00/0.09 | 0.04/1.00/0.08 | 0.12/1.00/0.21 |
| KB5 | 0.46/1.00/0.63 | n/a | n/a | 0.45/1.00/0.62 | 0.46/1.00/0.63 | 0.46/1.00/0.63 |

### QuAcq (example-first)
## Table: Exact equivalence of the delivered theory (folds attaining / scored); `--` = not measured, `0/n` = measured and none attained - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB2 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB4 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| KB5 | 0/3 | n/a | n/a | 0/3 | 0/3 | 0/3 |

## Table: Trivial baseline — accept-everything accuracy (Incremental Mode)

`baseline` = mean over folds of the test split's positive share; an accept-everything KB scores exactly this. `pooled` merges the test splits first and is shown for reference only — it is not what an accuracy cell is compared against.

| Method | KB | Strategy | baseline (fold mean) | pooled | reported accuracy |
|:---|:---|:---|---:|---:|---:|
| ConGen | REAL-FM-4 | 2cov | 0.0476 | 0.0556 | 0.9524 |
| QuAcq (example-first) | REAL-FM-4 | 2cov | 0.0476 | 0.0556 | 0.9444 |
| QuAcq (example-only) | REAL-FM-4 | 2cov | 0.0476 | 0.0556 | 0.9444 |
| ConGen | REAL-FM-4 | ff | 0.9383 | 0.9381 | 0.7159 |
| QuAcq (example-first) | REAL-FM-4 | ff | 0.9383 | 0.9381 | 1.0000 |
| QuAcq (example-only) | REAL-FM-4 | ff | 0.9383 | 0.9381 | 0.9734 |
| ConGen | REAL-FM-4 | rs_1n | 0.9004 | 0.9003 | 0.8243 |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 0.9004 | 0.9003 | 0.9966 |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 0.9004 | 0.9003 | 0.9897 |
| ConGen | REAL-FM-4 | rs_2n | 0.9004 | 0.9003 | 0.8934 |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 0.9004 | 0.9003 | 1.0000 |
| QuAcq (example-only) | REAL-FM-4 | rs_2n | 0.9004 | 0.9003 | 0.9880 |
| ConGen | REAL-FM-4 | rs_3n | 0.9003 | 0.9003 | 0.9244 |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 0.9003 | 0.9003 | 0.9989 |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 0.9003 | 0.9003 | 0.9954 |
| ConGen | REAL-FM-4 | rs_m | 0.9524 | 0.9444 | 0.2175 |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 0.9524 | 0.9444 | 1.0000 |
| QuAcq (example-only) | REAL-FM-4 | rs_m | 0.9524 | 0.9444 | 0.9524 |
| ConGen | REAL-FM-7 | 2cov | 0.0000 | 0.0000 | 1.0000 |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 0.0000 | 0.0000 | 0.8889 |
| QuAcq (example-only) | REAL-FM-7 | 2cov | 0.0000 | 0.0000 | 0.6667 |
| ConGen | REAL-FM-7 | ff | 0.6667 | 0.6667 | 0.3333 |
| QuAcq (example-first) | REAL-FM-7 | ff | 0.6667 | 0.6667 | 1.0000 |
| QuAcq (example-only) | REAL-FM-7 | ff | 0.6667 | 0.6667 | 0.7778 |
| ConGen | REAL-FM-7 | rs_1n | 0.9444 | 0.9286 | 0.2778 |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 0.9444 | 0.9286 | 1.0000 |
| QuAcq (example-only) | REAL-FM-7 | rs_1n | 0.9444 | 0.9286 | 0.9444 |
| ConGen | REAL-FM-7 | rs_2n | 0.9333 | 0.9286 | 0.5583 |
| QuAcq (example-first) | REAL-FM-7 | rs_2n | 0.9333 | 0.9286 | 0.9667 |
| QuAcq (example-only) | REAL-FM-7 | rs_2n | 0.9333 | 0.9286 | 0.9333 |
| ConGen | REAL-FM-7 | rs_3n | 0.9061 | 0.9048 | 0.8603 |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 0.9061 | 0.9048 | 0.9744 |
| QuAcq (example-only) | REAL-FM-7 | rs_3n | 0.9061 | 0.9048 | 0.9521 |
| ConGen | REAL-FM-7 | rs_m | 0.9167 | 0.8889 | 0.1944 |
| QuAcq (example-first) | REAL-FM-7 | rs_m | 0.9167 | 0.8889 | 0.9167 |
| QuAcq (example-only) | REAL-FM-7 | rs_m | 0.9167 | 0.8889 | 0.9167 |
| ConGen | arcade-game | 2cov | 0.0556 | 0.0714 | 0.9444 |
| QuAcq (example-first) | arcade-game | 2cov | 0.0556 | 0.0714 | 0.9444 |
| QuAcq (example-only) | arcade-game | 2cov | 0.0556 | 0.0714 | 0.8611 |
| ConGen | arcade-game | ff | 0.8357 | 0.8333 | 0.3189 |
| QuAcq (example-first) | arcade-game | ff | 0.8357 | 0.8333 | 1.0000 |
| QuAcq (example-only) | arcade-game | ff | 0.8357 | 0.8333 | 0.9024 |
| ConGen | arcade-game | rs_1n | 0.9076 | 0.9077 | 0.4149 |
| QuAcq (example-first) | arcade-game | rs_1n | 0.9076 | 0.9077 | 1.0000 |
| QuAcq (example-only) | arcade-game | rs_1n | 0.9076 | 0.9077 | 0.9690 |
| ConGen | arcade-game | rs_2n | 0.9001 | 0.9000 | 0.5086 |
| QuAcq (example-first) | arcade-game | rs_2n | 0.9001 | 0.9000 | 1.0000 |
| QuAcq (example-only) | arcade-game | rs_2n | 0.9001 | 0.9000 | 0.9693 |
| ConGen | arcade-game | rs_3n | 0.9026 | 0.9026 | 0.5542 |
| QuAcq (example-first) | arcade-game | rs_3n | 0.9026 | 0.9026 | 1.0000 |
| QuAcq (example-only) | arcade-game | rs_3n | 0.9026 | 0.9026 | 0.9949 |
| ConGen | arcade-game | rs_m | 0.9444 | 0.9286 | 0.1944 |
| QuAcq (example-first) | arcade-game | rs_m | 0.9444 | 0.9286 | 1.0000 |
| QuAcq (example-only) | arcade-game | rs_m | 0.9444 | 0.9286 | 0.9444 |
| ConGen | busybox-1.18.0 | 2cov | 0.0000 | 0.0000 | 1.0000 |
| QuAcq (example-first) | busybox-1.18.0 | 2cov | 0.0000 | 0.0000 | 0.9048 |
| QuAcq (example-only) | busybox-1.18.0 | 2cov | 0.0000 | 0.0000 | 0.9048 |
| ConGen | busybox-1.18.0 | ff | 0.9776 | 0.9776 | 0.7057 |
| QuAcq (example-first) | busybox-1.18.0 | ff | 0.9776 | 0.9776 | 1.0000 |
| QuAcq (example-only) | busybox-1.18.0 | ff | 0.9776 | 0.9776 | 0.9900 |
| ConGen | busybox-1.18.0 | rs_1n | 0.9005 | 0.9005 | 0.8665 |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 0.9005 | 0.9005 | 0.9977 |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 0.9005 | 0.9005 | 0.9906 |
| ConGen | busybox-1.18.0 | rs_m | 0.9107 | 0.9048 | 0.0893 |
| QuAcq (example-first) | busybox-1.18.0 | rs_m | 0.9107 | 0.9048 | 0.9583 |
| QuAcq (example-only) | busybox-1.18.0 | rs_m | 0.9107 | 0.9048 | 0.9583 |
| ConGen | fqa | 2cov | 0.0000 | 0.0000 | 1.0000 |
| QuAcq (example-first) | fqa | 2cov | 0.0000 | 0.0000 | 0.9333 |
| QuAcq (example-only) | fqa | 2cov | 0.0000 | 0.0000 | 0.9333 |
| ConGen | fqa | ff | 0.9004 | 0.9000 | 0.8134 |
| QuAcq (example-first) | fqa | ff | 0.9004 | 0.9000 | 1.0000 |
| QuAcq (example-only) | fqa | ff | 0.9004 | 0.9000 | 0.9716 |
| ConGen | fqa | rs_1n | 0.9051 | 0.9050 | 0.8543 |
| QuAcq (example-first) | fqa | rs_1n | 0.9051 | 0.9050 | 1.0000 |
| QuAcq (example-only) | fqa | rs_1n | 0.9051 | 0.9050 | 0.9610 |
| ConGen | fqa | rs_2n | 0.9023 | 0.9022 | 0.9271 |
| QuAcq (example-first) | fqa | rs_2n | 0.9023 | 0.9022 | 1.0000 |
| QuAcq (example-only) | fqa | rs_2n | 0.9023 | 0.9022 | 0.9972 |
| ConGen | fqa | rs_3n | 0.9013 | 0.9013 | 0.9665 |
| QuAcq (example-first) | fqa | rs_3n | 0.9013 | 0.9013 | 1.0000 |
| QuAcq (example-only) | fqa | rs_3n | 0.9013 | 0.9013 | 0.9981 |
| ConGen | fqa | rs_m | 0.9444 | 0.9375 | 0.3667 |
| QuAcq (example-first) | fqa | rs_m | 0.9444 | 0.9375 | 1.0000 |
| QuAcq (example-only) | fqa | rs_m | 0.9444 | 0.9375 | 1.0000 |

## Table: Fold agreement (Incremental Mode)

Share of the delivered knowledge base present in ALL folds (|intersection| / mean fold |KB|). A reliability statistic, not a quality score: the intersection is a subset of every fold's KB, so its recall can only fall, and it shrinks as the number of folds grows.

| Method | KB | Strategy | mean \|KB\| | in all folds | agreement |
|:---|:---|:---|---:|---:|---:|
| ConGen | REAL-FM-4 | ff | 230.3 | 156 | 68% |
| QuAcq (example-first) | REAL-FM-4 | ff | 26.3 | 6 | 23% |
| ConGen | REAL-FM-4 | rs_1n | 242.7 | 171 | 70% |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 12.3 | 1 | 8% |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 3.3 | 1 | 30% |
| ConGen | REAL-FM-4 | rs_2n | 248.7 | 184 | 74% |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 31.7 | 6 | 19% |
| ConGen | REAL-FM-4 | rs_3n | 237.0 | 180 | 76% |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 9.7 | 3 | 31% |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 3.7 | 3 | 82% |
| ConGen | REAL-FM-4 | rs_m | 222.0 | 139 | 63% |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 10.0 | 1 | 10% |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 3.3 | 3 | 90% |
| QuAcq (example-first) | REAL-FM-7 | ff | 3.0 | 1 | 33% |
| ConGen | REAL-FM-7 | rs_1n | 18.3 | 1 | 5% |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 3.0 | 2 | 67% |
| ConGen | REAL-FM-7 | rs_2n | 18.7 | 3 | 16% |
| ConGen | REAL-FM-7 | rs_3n | 13.0 | 1 | 8% |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 3.0 | 2 | 67% |
| ConGen | arcade-game | 2cov | 47.7 | 2 | 4% |
| QuAcq (example-first) | arcade-game | 2cov | 20.3 | 4 | 20% |
| QuAcq (example-only) | arcade-game | 2cov | 3.0 | 1 | 33% |
| ConGen | arcade-game | ff | 101.7 | 28 | 28% |
| QuAcq (example-first) | arcade-game | ff | 22.3 | 6 | 27% |
| ConGen | arcade-game | rs_1n | 176.7 | 51 | 29% |
| QuAcq (example-first) | arcade-game | rs_1n | 32.7 | 16 | 49% |
| ConGen | arcade-game | rs_2n | 243.0 | 132 | 54% |
| QuAcq (example-first) | arcade-game | rs_2n | 27.7 | 14 | 51% |
| QuAcq (example-only) | arcade-game | rs_2n | 1.7 | 1 | 60% |
| ConGen | arcade-game | rs_3n | 224.3 | 133 | 59% |
| QuAcq (example-first) | arcade-game | rs_3n | 40.7 | 23 | 57% |
| QuAcq (example-only) | arcade-game | rs_3n | 2.7 | 1 | 38% |
| ConGen | arcade-game | rs_m | 74.3 | 26 | 35% |
| QuAcq (example-first) | arcade-game | rs_m | 26.3 | 10 | 38% |
| ConGen | busybox-1.18.0 | ff | 647.3 | 389 | 60% |
| ConGen | busybox-1.18.0 | rs_1n | 687.0 | 568 | 83% |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 15.3 | 6 | 39% |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 8.7 | 6 | 69% |
| ConGen | busybox-1.18.0 | rs_m | 484.7 | 304 | 63% |
| ConGen | fqa | 2cov | 104.3 | 41 | 39% |
| QuAcq (example-first) | fqa | 2cov | 11.0 | 3 | 27% |
| QuAcq (example-only) | fqa | 2cov | 1.7 | 1 | 60% |
| ConGen | fqa | ff | 120.7 | 92 | 76% |
| QuAcq (example-first) | fqa | ff | 17.3 | 3 | 17% |
| ConGen | fqa | rs_1n | 130.7 | 104 | 80% |
| QuAcq (example-first) | fqa | rs_1n | 17.3 | 5 | 29% |
| QuAcq (example-only) | fqa | rs_1n | 2.3 | 1 | 43% |
| ConGen | fqa | rs_2n | 135.0 | 113 | 84% |
| QuAcq (example-first) | fqa | rs_2n | 19.0 | 4 | 21% |
| QuAcq (example-only) | fqa | rs_2n | 3.3 | 2 | 60% |
| ConGen | fqa | rs_3n | 136.0 | 124 | 91% |
| QuAcq (example-first) | fqa | rs_3n | 15.0 | 3 | 20% |
| QuAcq (example-only) | fqa | rs_3n | 3.3 | 2 | 60% |
| ConGen | fqa | rs_m | 108.3 | 80 | 74% |
| QuAcq (example-first) | fqa | rs_m | 16.0 | 5 | 31% |

## Table: Semantic tier — absolute counts (Incremental Mode)

`|Cτ|` = target clauses = tp + fn. `fp` = delivered but not entailed (review workload). `fn` = entailed by the target but missing (authoring workload).

| Method | KB | Strategy | \|Cτ\| | tp | fp | fn | R | P | F1 |
|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|
| ConGen | REAL-FM-4 | 2cov | 428 | 428 | 67 | 0 | 1.0000 | 0.8724 | 0.9297 |
| QuAcq (example-first) | REAL-FM-4 | 2cov | 428 | 17 | 0 | 411 | 0.0405 | 1.0000 | 0.0768 |
| QuAcq (example-only) | REAL-FM-4 | 2cov | 428 | 9 | 0 | 419 | 0.0210 | 1.0000 | 0.0410 |
| ConGen | REAL-FM-4 | ff | 428 | 428 | 200 | 0 | 1.0000 | 0.6831 | 0.8113 |
| QuAcq (example-first) | REAL-FM-4 | ff | 428 | 50 | 0 | 378 | 0.1176 | 1.0000 | 0.2096 |
| QuAcq (example-only) | REAL-FM-4 | ff | 428 | 5 | 0 | 423 | 0.0117 | 1.0000 | 0.0231 |
| ConGen | REAL-FM-4 | rs_1n | 428 | 417 | 176 | 11 | 0.9743 | 0.7038 | 0.8169 |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 428 | 24 | 0 | 404 | 0.0569 | 1.0000 | 0.1065 |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 428 | 8 | 0 | 420 | 0.0187 | 1.0000 | 0.0367 |
| ConGen | REAL-FM-4 | rs_2n | 428 | 428 | 123 | 0 | 1.0000 | 0.7788 | 0.8751 |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 428 | 62 | 0 | 366 | 0.1456 | 0.9938 | 0.2515 |
| QuAcq (example-only) | REAL-FM-4 | rs_2n | 428 | 9 | 0 | 419 | 0.0202 | 1.0000 | 0.0397 |
| ConGen | REAL-FM-4 | rs_3n | 428 | 428 | 100 | 0 | 1.0000 | 0.8122 | 0.8961 |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 428 | 20 | 0 | 408 | 0.0475 | 1.0000 | 0.0897 |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 428 | 9 | 0 | 419 | 0.0202 | 1.0000 | 0.0397 |
| ConGen | REAL-FM-4 | rs_m | 428 | 428 | 210 | 0 | 1.0000 | 0.6719 | 0.8034 |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 428 | 20 | 0 | 408 | 0.0467 | 1.0000 | 0.0883 |
| QuAcq (example-only) | REAL-FM-4 | rs_m | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 |
| ConGen | REAL-FM-7 | 2cov | 22 | 21 | 6 | 1 | 0.9394 | 0.7747 | 0.8489 |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 22 | 11 | 0 | 11 | 0.5152 | 1.0000 | 0.6797 |
| QuAcq (example-only) | REAL-FM-7 | 2cov | 22 | 7 | 0 | 15 | 0.3030 | 1.0000 | 0.4647 |
| ConGen | REAL-FM-7 | ff | 22 | 22 | 8 | 0 | 1.0000 | 0.7418 | 0.8517 |
| QuAcq (example-first) | REAL-FM-7 | ff | 22 | 10 | 0 | 12 | 0.4697 | 1.0000 | 0.6380 |
| QuAcq (example-only) | REAL-FM-7 | ff | 22 | 7 | 0 | 15 | 0.3333 | 1.0000 | 0.4996 |
| ConGen | REAL-FM-7 | rs_1n | 22 | 22 | 6 | 0 | 1.0000 | 0.7780 | 0.8747 |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6658 |
| QuAcq (example-only) | REAL-FM-7 | rs_1n | 22 | 7 | 0 | 15 | 0.3030 | 1.0000 | 0.4647 |
| ConGen | REAL-FM-7 | rs_2n | 22 | 22 | 5 | 0 | 1.0000 | 0.8171 | 0.8987 |
| QuAcq (example-first) | REAL-FM-7 | rs_2n | 22 | 9 | 0 | 13 | 0.3939 | 1.0000 | 0.5609 |
| QuAcq (example-only) | REAL-FM-7 | rs_2n | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 |
| ConGen | REAL-FM-7 | rs_3n | 22 | 22 | 2 | 0 | 0.9848 | 0.9306 | 0.9565 |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6658 |
| QuAcq (example-only) | REAL-FM-7 | rs_3n | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 |
| ConGen | REAL-FM-7 | rs_m | 22 | 20 | 9 | 2 | 0.8939 | 0.6849 | 0.7754 |
| QuAcq (example-first) | REAL-FM-7 | rs_m | 22 | 9 | 0 | 13 | 0.4091 | 1.0000 | 0.5740 |
| QuAcq (example-only) | REAL-FM-7 | rs_m | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 |
| ConGen | arcade-game | 2cov | 130 | 97 | 28 | 33 | 0.7462 | 0.7666 | 0.7048 |
| QuAcq (example-first) | arcade-game | 2cov | 130 | 39 | 0 | 91 | 0.3000 | 1.0000 | 0.4405 |
| QuAcq (example-only) | arcade-game | 2cov | 130 | 11 | 0 | 119 | 0.0821 | 1.0000 | 0.1509 |
| ConGen | arcade-game | ff | 130 | 128 | 96 | 2 | 0.9821 | 0.5805 | 0.7268 |
| QuAcq (example-first) | arcade-game | ff | 130 | 52 | 0 | 78 | 0.3974 | 1.0000 | 0.5601 |
| QuAcq (example-only) | arcade-game | ff | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0596 |
| ConGen | arcade-game | rs_1n | 130 | 126 | 126 | 4 | 0.9692 | 0.5001 | 0.6597 |
| QuAcq (example-first) | arcade-game | rs_1n | 130 | 61 | 0 | 69 | 0.4718 | 1.0000 | 0.6300 |
| QuAcq (example-only) | arcade-game | rs_1n | 130 | 4 | 0 | 126 | 0.0333 | 1.0000 | 0.0645 |
| ConGen | arcade-game | rs_2n | 130 | 128 | 184 | 2 | 0.9846 | 0.4109 | 0.5798 |
| QuAcq (example-first) | arcade-game | rs_2n | 130 | 52 | 0 | 78 | 0.3974 | 1.0000 | 0.5643 |
| QuAcq (example-only) | arcade-game | rs_2n | 130 | 5 | 0 | 125 | 0.0359 | 1.0000 | 0.0693 |
| ConGen | arcade-game | rs_3n | 130 | 126 | 166 | 4 | 0.9667 | 0.4303 | 0.5955 |
| QuAcq (example-first) | arcade-game | rs_3n | 130 | 78 | 0 | 52 | 0.6026 | 1.0000 | 0.7493 |
| QuAcq (example-only) | arcade-game | rs_3n | 130 | 9 | 0 | 121 | 0.0692 | 1.0000 | 0.1287 |
| ConGen | arcade-game | rs_m | 130 | 130 | 68 | 0 | 1.0000 | 0.6849 | 0.8058 |
| QuAcq (example-first) | arcade-game | rs_m | 130 | 45 | 0 | 85 | 0.3487 | 1.0000 | 0.5153 |
| QuAcq (example-only) | arcade-game | rs_m | 130 | 4 | 0 | 126 | 0.0282 | 1.0000 | 0.0548 |
| ConGen | busybox-1.18.0 | 2cov | 994 | 994 | 6 | 0 | 1.0000 | 0.9943 | 0.9972 |
| QuAcq (example-first) | busybox-1.18.0 | 2cov | 994 | 452 | 0 | 542 | 0.4551 | 1.0000 | 0.6255 |
| QuAcq (example-only) | busybox-1.18.0 | 2cov | 994 | 446 | 0 | 548 | 0.4484 | 1.0000 | 0.6191 |
| ConGen | busybox-1.18.0 | ff | 994 | 994 | 245 | 0 | 1.0000 | 0.8034 | 0.8907 |
| QuAcq (example-first) | busybox-1.18.0 | ff | 994 | 458 | 0 | 536 | 0.4604 | 1.0000 | 0.6305 |
| QuAcq (example-only) | busybox-1.18.0 | ff | 994 | 447 | 0 | 547 | 0.4494 | 1.0000 | 0.6201 |
| ConGen | busybox-1.18.0 | rs_1n | 994 | 992 | 235 | 2 | 0.9983 | 0.8091 | 0.8937 |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 994 | 461 | 0 | 533 | 0.4638 | 1.0000 | 0.6337 |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 994 | 454 | 0 | 540 | 0.4564 | 1.0000 | 0.6268 |
| ConGen | busybox-1.18.0 | rs_m | 994 | 994 | 204 | 0 | 1.0000 | 0.8295 | 0.9068 |
| QuAcq (example-first) | busybox-1.18.0 | rs_m | 994 | 449 | 0 | 545 | 0.4514 | 1.0000 | 0.6220 |
| QuAcq (example-only) | busybox-1.18.0 | rs_m | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 |
| ConGen | fqa | 2cov | 342 | 342 | 105 | 0 | 1.0000 | 0.7651 | 0.8669 |
| QuAcq (example-first) | fqa | 2cov | 342 | 26 | 0 | 316 | 0.0770 | 1.0000 | 0.1413 |
| QuAcq (example-only) | fqa | 2cov | 342 | 9 | 0 | 333 | 0.0253 | 1.0000 | 0.0494 |
| ConGen | fqa | ff | 342 | 342 | 61 | 0 | 1.0000 | 0.8480 | 0.9177 |
| QuAcq (example-first) | fqa | ff | 342 | 38 | 0 | 304 | 0.1111 | 1.0000 | 0.1961 |
| QuAcq (example-only) | fqa | ff | 342 | 9 | 0 | 333 | 0.0253 | 1.0000 | 0.0494 |
| ConGen | fqa | rs_1n | 342 | 342 | 39 | 0 | 1.0000 | 0.8973 | 0.9458 |
| QuAcq (example-first) | fqa | rs_1n | 342 | 38 | 0 | 304 | 0.1111 | 1.0000 | 0.1999 |
| QuAcq (example-only) | fqa | rs_1n | 342 | 9 | 0 | 333 | 0.0273 | 1.0000 | 0.0531 |
| ConGen | fqa | rs_2n | 342 | 342 | 45 | 0 | 1.0000 | 0.8838 | 0.9383 |
| QuAcq (example-first) | fqa | rs_2n | 342 | 40 | 0 | 302 | 0.1160 | 1.0000 | 0.2023 |
| QuAcq (example-only) | fqa | rs_2n | 342 | 11 | 0 | 331 | 0.0331 | 1.0000 | 0.0641 |
| ConGen | fqa | rs_3n | 342 | 342 | 35 | 0 | 1.0000 | 0.9072 | 0.9513 |
| QuAcq (example-first) | fqa | rs_3n | 342 | 33 | 0 | 309 | 0.0965 | 1.0000 | 0.1755 |
| QuAcq (example-only) | fqa | rs_3n | 342 | 11 | 0 | 331 | 0.0331 | 1.0000 | 0.0641 |
| ConGen | fqa | rs_m | 342 | 342 | 45 | 0 | 1.0000 | 0.8845 | 0.9387 |
| QuAcq (example-first) | fqa | rs_m | 342 | 36 | 0 | 306 | 0.1053 | 1.0000 | 0.1899 |
| QuAcq (example-only) | fqa | rs_m | 342 | 6 | 0 | 336 | 0.0175 | 1.0000 | 0.0345 |

## Table: Semantic tier per fold — R/P/F1 (Incremental Mode)

| Method | KB | Strategy | Fold | \|Cτ\| | tp | fp | fn | R | P | F1 | eq |
|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| ConGen | REAL-FM-4 | 2cov | 0 | 428 | 428 | 3 | 0 | 1.0000 | 0.9930 | 0.9965 | 0 |
| ConGen | REAL-FM-4 | 2cov | 1 | 428 | 428 | 98 | 0 | 1.0000 | 0.8137 | 0.8973 | 0 |
| ConGen | REAL-FM-4 | 2cov | 2 | 428 | 428 | 100 | 0 | 1.0000 | 0.8106 | 0.8954 | 0 |
| QuAcq (example-first) | REAL-FM-4 | 2cov | 0 | 428 | 23 | 0 | 405 | 0.0537 | 1.0000 | 0.1020 | 0 |
| QuAcq (example-first) | REAL-FM-4 | 2cov | 1 | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 | 0 |
| QuAcq (example-first) | REAL-FM-4 | 2cov | 2 | 428 | 26 | 0 | 402 | 0.0607 | 1.0000 | 0.1145 | 0 |
| QuAcq (example-only) | REAL-FM-4 | 2cov | 0 | 428 | 12 | 0 | 416 | 0.0280 | 1.0000 | 0.0545 | 0 |
| QuAcq (example-only) | REAL-FM-4 | 2cov | 1 | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 | 0 |
| QuAcq (example-only) | REAL-FM-4 | 2cov | 2 | 428 | 12 | 0 | 416 | 0.0280 | 1.0000 | 0.0545 | 0 |
| ConGen | REAL-FM-4 | ff | 0 | 428 | 428 | 185 | 0 | 1.0000 | 0.6982 | 0.8223 | 0 |
| ConGen | REAL-FM-4 | ff | 1 | 428 | 428 | 172 | 0 | 1.0000 | 0.7133 | 0.8327 | 0 |
| ConGen | REAL-FM-4 | ff | 2 | 428 | 428 | 243 | 0 | 1.0000 | 0.6379 | 0.7789 | 0 |
| QuAcq (example-first) | REAL-FM-4 | ff | 0 | 428 | 38 | 0 | 390 | 0.0888 | 1.0000 | 0.1631 | 0 |
| QuAcq (example-first) | REAL-FM-4 | ff | 1 | 428 | 63 | 0 | 365 | 0.1472 | 1.0000 | 0.2566 | 0 |
| QuAcq (example-first) | REAL-FM-4 | ff | 2 | 428 | 50 | 0 | 378 | 0.1168 | 1.0000 | 0.2092 | 0 |
| QuAcq (example-only) | REAL-FM-4 | ff | 0 | 428 | 5 | 0 | 423 | 0.0117 | 1.0000 | 0.0231 | 0 |
| QuAcq (example-only) | REAL-FM-4 | ff | 1 | 428 | 4 | 0 | 424 | 0.0093 | 1.0000 | 0.0185 | 0 |
| QuAcq (example-only) | REAL-FM-4 | ff | 2 | 428 | 6 | 0 | 422 | 0.0140 | 1.0000 | 0.0276 | 0 |
| ConGen | REAL-FM-4 | rs_1n | 0 | 428 | 428 | 185 | 0 | 1.0000 | 0.6982 | 0.8223 | 0 |
| ConGen | REAL-FM-4 | rs_1n | 1 | 428 | 395 | 161 | 33 | 0.9229 | 0.7104 | 0.8028 | 0 |
| ConGen | REAL-FM-4 | rs_1n | 2 | 428 | 428 | 181 | 0 | 1.0000 | 0.7028 | 0.8255 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 0 | 428 | 10 | 0 | 418 | 0.0234 | 1.0000 | 0.0457 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 1 | 428 | 36 | 0 | 392 | 0.0841 | 1.0000 | 0.1552 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_1n | 2 | 428 | 27 | 0 | 401 | 0.0631 | 1.0000 | 0.1187 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 0 | 428 | 8 | 0 | 420 | 0.0187 | 1.0000 | 0.0367 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 1 | 428 | 9 | 0 | 419 | 0.0210 | 1.0000 | 0.0412 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_1n | 2 | 428 | 7 | 0 | 421 | 0.0164 | 1.0000 | 0.0322 | 0 |
| ConGen | REAL-FM-4 | rs_2n | 0 | 428 | 428 | 96 | 0 | 1.0000 | 0.8168 | 0.8992 | 0 |
| ConGen | REAL-FM-4 | rs_2n | 1 | 428 | 428 | 162 | 0 | 1.0000 | 0.7254 | 0.8409 | 0 |
| ConGen | REAL-FM-4 | rs_2n | 2 | 428 | 428 | 111 | 0 | 1.0000 | 0.7941 | 0.8852 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 0 | 428 | 53 | 1 | 375 | 0.1238 | 0.9815 | 0.2199 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 1 | 428 | 89 | 0 | 339 | 0.2079 | 1.0000 | 0.3443 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_2n | 2 | 428 | 45 | 0 | 383 | 0.1051 | 1.0000 | 0.1903 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_2n | 0 | 428 | 10 | 0 | 418 | 0.0234 | 1.0000 | 0.0457 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_2n | 1 | 428 | 7 | 0 | 421 | 0.0164 | 1.0000 | 0.0322 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_2n | 2 | 428 | 9 | 0 | 419 | 0.0210 | 1.0000 | 0.0412 | 0 |
| ConGen | REAL-FM-4 | rs_3n | 0 | 428 | 428 | 78 | 0 | 1.0000 | 0.8458 | 0.9165 | 0 |
| ConGen | REAL-FM-4 | rs_3n | 1 | 428 | 428 | 96 | 0 | 1.0000 | 0.8168 | 0.8992 | 0 |
| ConGen | REAL-FM-4 | rs_3n | 2 | 428 | 428 | 125 | 0 | 1.0000 | 0.7740 | 0.8726 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 0 | 428 | 14 | 0 | 414 | 0.0327 | 1.0000 | 0.0633 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 1 | 428 | 35 | 0 | 393 | 0.0818 | 1.0000 | 0.1512 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_3n | 2 | 428 | 12 | 0 | 416 | 0.0280 | 1.0000 | 0.0545 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 0 | 428 | 9 | 0 | 419 | 0.0210 | 1.0000 | 0.0412 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 1 | 428 | 8 | 0 | 420 | 0.0187 | 1.0000 | 0.0367 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_3n | 2 | 428 | 9 | 0 | 419 | 0.0210 | 1.0000 | 0.0412 | 0 |
| ConGen | REAL-FM-4 | rs_m | 0 | 428 | 428 | 198 | 0 | 1.0000 | 0.6837 | 0.8121 | 0 |
| ConGen | REAL-FM-4 | rs_m | 1 | 428 | 428 | 251 | 0 | 1.0000 | 0.6303 | 0.7733 | 0 |
| ConGen | REAL-FM-4 | rs_m | 2 | 428 | 428 | 182 | 0 | 1.0000 | 0.7016 | 0.8247 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 0 | 428 | 19 | 0 | 409 | 0.0444 | 1.0000 | 0.0850 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 1 | 428 | 8 | 0 | 420 | 0.0187 | 1.0000 | 0.0367 | 0 |
| QuAcq (example-first) | REAL-FM-4 | rs_m | 2 | 428 | 33 | 0 | 395 | 0.0771 | 1.0000 | 0.1432 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_m | 0 | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_m | 1 | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 | 0 |
| QuAcq (example-only) | REAL-FM-4 | rs_m | 2 | 428 | 3 | 0 | 425 | 0.0070 | 1.0000 | 0.0139 | 0 |
| ConGen | REAL-FM-7 | 2cov | 0 | 22 | 22 | 6 | 0 | 1.0000 | 0.7857 | 0.8800 | 0 |
| ConGen | REAL-FM-7 | 2cov | 1 | 22 | 18 | 8 | 4 | 0.8182 | 0.6923 | 0.7500 | 0 |
| ConGen | REAL-FM-7 | 2cov | 2 | 22 | 22 | 4 | 0 | 1.0000 | 0.8462 | 0.9167 | 0 |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 0 | 22 | 12 | 0 | 10 | 0.5455 | 1.0000 | 0.7059 | 0 |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 1 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | REAL-FM-7 | 2cov | 2 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-only) | REAL-FM-7 | 2cov | 0 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | 2cov | 1 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| QuAcq (example-only) | REAL-FM-7 | 2cov | 2 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| ConGen | REAL-FM-7 | ff | 0 | 22 | 22 | 8 | 0 | 1.0000 | 0.7333 | 0.8462 | 0 |
| ConGen | REAL-FM-7 | ff | 1 | 22 | 22 | 8 | 0 | 1.0000 | 0.7333 | 0.8462 | 0 |
| ConGen | REAL-FM-7 | ff | 2 | 22 | 22 | 7 | 0 | 1.0000 | 0.7586 | 0.8627 | 0 |
| QuAcq (example-first) | REAL-FM-7 | ff | 0 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | REAL-FM-7 | ff | 1 | 22 | 9 | 0 | 13 | 0.4091 | 1.0000 | 0.5806 | 0 |
| QuAcq (example-first) | REAL-FM-7 | ff | 2 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-only) | REAL-FM-7 | ff | 0 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| QuAcq (example-only) | REAL-FM-7 | ff | 1 | 22 | 8 | 0 | 14 | 0.3636 | 1.0000 | 0.5333 | 0 |
| QuAcq (example-only) | REAL-FM-7 | ff | 2 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| ConGen | REAL-FM-7 | rs_1n | 0 | 22 | 22 | 8 | 0 | 1.0000 | 0.7333 | 0.8462 | 0 |
| ConGen | REAL-FM-7 | rs_1n | 1 | 22 | 22 | 6 | 0 | 1.0000 | 0.7857 | 0.8800 | 0 |
| ConGen | REAL-FM-7 | rs_1n | 2 | 22 | 22 | 5 | 0 | 1.0000 | 0.8148 | 0.8980 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 0 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 1 | 22 | 10 | 0 | 12 | 0.4545 | 1.0000 | 0.6250 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_1n | 2 | 22 | 12 | 0 | 10 | 0.5455 | 1.0000 | 0.7059 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_1n | 0 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_1n | 1 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_1n | 2 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| ConGen | REAL-FM-7 | rs_2n | 0 | 22 | 22 | 6 | 0 | 1.0000 | 0.7857 | 0.8800 | 0 |
| ConGen | REAL-FM-7 | rs_2n | 1 | 22 | 22 | 3 | 0 | 1.0000 | 0.8800 | 0.9362 | 0 |
| ConGen | REAL-FM-7 | rs_2n | 2 | 22 | 22 | 6 | 0 | 1.0000 | 0.7857 | 0.8800 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_2n | 0 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_2n | 1 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_2n | 2 | 22 | 8 | 0 | 14 | 0.3636 | 1.0000 | 0.5333 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_2n | 0 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_2n | 1 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_2n | 2 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| ConGen | REAL-FM-7 | rs_3n | 0 | 22 | 22 | 2 | 0 | 1.0000 | 0.9167 | 0.9565 | 0 |
| ConGen | REAL-FM-7 | rs_3n | 1 | 22 | 21 | 3 | 1 | 0.9545 | 0.8750 | 0.9130 | 0 |
| ConGen | REAL-FM-7 | rs_3n | 2 | 22 | 22 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1 |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 0 | 22 | 12 | 0 | 10 | 0.5455 | 1.0000 | 0.7059 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 1 | 22 | 11 | 0 | 11 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_3n | 2 | 22 | 10 | 0 | 12 | 0.4545 | 1.0000 | 0.6250 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_3n | 0 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_3n | 1 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_3n | 2 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| ConGen | REAL-FM-7 | rs_m | 0 | 22 | 22 | 8 | 0 | 1.0000 | 0.7333 | 0.8462 | 0 |
| ConGen | REAL-FM-7 | rs_m | 1 | 22 | 21 | 7 | 1 | 0.9545 | 0.7500 | 0.8400 | 0 |
| ConGen | REAL-FM-7 | rs_m | 2 | 22 | 16 | 12 | 6 | 0.7273 | 0.5714 | 0.6400 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_m | 0 | 22 | 8 | 0 | 14 | 0.3636 | 1.0000 | 0.5333 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_m | 1 | 22 | 12 | 0 | 10 | 0.5455 | 1.0000 | 0.7059 | 0 |
| QuAcq (example-first) | REAL-FM-7 | rs_m | 2 | 22 | 7 | 0 | 15 | 0.3182 | 1.0000 | 0.4828 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_m | 0 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_m | 1 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| QuAcq (example-only) | REAL-FM-7 | rs_m | 2 | 22 | 6 | 0 | 16 | 0.2727 | 1.0000 | 0.4286 | 0 |
| ConGen | arcade-game | 2cov | 0 | 130 | 31 | 11 | 99 | 0.2385 | 0.7381 | 0.3605 | 0 |
| ConGen | arcade-game | 2cov | 1 | 130 | 130 | 36 | 0 | 1.0000 | 0.7831 | 0.8784 | 0 |
| ConGen | arcade-game | 2cov | 2 | 130 | 130 | 37 | 0 | 1.0000 | 0.7784 | 0.8754 | 0 |
| QuAcq (example-first) | arcade-game | 2cov | 0 | 130 | 18 | 0 | 112 | 0.1385 | 1.0000 | 0.2432 | 0 |
| QuAcq (example-first) | arcade-game | 2cov | 1 | 130 | 66 | 0 | 64 | 0.5077 | 1.0000 | 0.6735 | 0 |
| QuAcq (example-first) | arcade-game | 2cov | 2 | 130 | 33 | 0 | 97 | 0.2538 | 1.0000 | 0.4049 | 0 |
| QuAcq (example-only) | arcade-game | 2cov | 0 | 130 | 14 | 0 | 116 | 0.1077 | 1.0000 | 0.1944 | 0 |
| QuAcq (example-only) | arcade-game | 2cov | 1 | 130 | 11 | 0 | 119 | 0.0846 | 1.0000 | 0.1560 | 0 |
| QuAcq (example-only) | arcade-game | 2cov | 2 | 130 | 7 | 0 | 123 | 0.0538 | 1.0000 | 0.1022 | 0 |
| ConGen | arcade-game | ff | 0 | 130 | 123 | 82 | 7 | 0.9462 | 0.6000 | 0.7343 | 0 |
| ConGen | arcade-game | ff | 1 | 130 | 130 | 68 | 0 | 1.0000 | 0.6566 | 0.7927 | 0 |
| ConGen | arcade-game | ff | 2 | 130 | 130 | 138 | 0 | 1.0000 | 0.4851 | 0.6533 | 0 |
| QuAcq (example-first) | arcade-game | ff | 0 | 130 | 72 | 0 | 58 | 0.5538 | 1.0000 | 0.7129 | 0 |
| QuAcq (example-first) | arcade-game | ff | 1 | 130 | 39 | 0 | 91 | 0.3000 | 1.0000 | 0.4615 | 0 |
| QuAcq (example-first) | arcade-game | ff | 2 | 130 | 44 | 0 | 86 | 0.3385 | 1.0000 | 0.5057 | 0 |
| QuAcq (example-only) | arcade-game | ff | 0 | 130 | 3 | 0 | 127 | 0.0231 | 1.0000 | 0.0451 | 0 |
| QuAcq (example-only) | arcade-game | ff | 1 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| QuAcq (example-only) | arcade-game | ff | 2 | 130 | 5 | 0 | 125 | 0.0385 | 1.0000 | 0.0741 | 0 |
| ConGen | arcade-game | rs_1n | 0 | 130 | 124 | 121 | 6 | 0.9538 | 0.5061 | 0.6613 | 0 |
| ConGen | arcade-game | rs_1n | 1 | 130 | 125 | 131 | 5 | 0.9615 | 0.4883 | 0.6477 | 0 |
| ConGen | arcade-game | rs_1n | 2 | 130 | 129 | 126 | 1 | 0.9923 | 0.5059 | 0.6701 | 0 |
| QuAcq (example-first) | arcade-game | rs_1n | 0 | 130 | 82 | 0 | 48 | 0.6308 | 1.0000 | 0.7736 | 0 |
| QuAcq (example-first) | arcade-game | rs_1n | 1 | 130 | 40 | 0 | 90 | 0.3077 | 1.0000 | 0.4706 | 0 |
| QuAcq (example-first) | arcade-game | rs_1n | 2 | 130 | 62 | 0 | 68 | 0.4769 | 1.0000 | 0.6458 | 0 |
| QuAcq (example-only) | arcade-game | rs_1n | 0 | 130 | 5 | 0 | 125 | 0.0385 | 1.0000 | 0.0741 | 0 |
| QuAcq (example-only) | arcade-game | rs_1n | 1 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| QuAcq (example-only) | arcade-game | rs_1n | 2 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| ConGen | arcade-game | rs_2n | 0 | 130 | 130 | 175 | 0 | 1.0000 | 0.4262 | 0.5977 | 0 |
| ConGen | arcade-game | rs_2n | 1 | 130 | 130 | 182 | 0 | 1.0000 | 0.4167 | 0.5882 | 0 |
| ConGen | arcade-game | rs_2n | 2 | 130 | 124 | 194 | 6 | 0.9538 | 0.3899 | 0.5536 | 0 |
| QuAcq (example-first) | arcade-game | rs_2n | 0 | 130 | 39 | 0 | 91 | 0.3000 | 1.0000 | 0.4615 | 0 |
| QuAcq (example-first) | arcade-game | rs_2n | 1 | 130 | 64 | 0 | 66 | 0.4923 | 1.0000 | 0.6598 | 0 |
| QuAcq (example-first) | arcade-game | rs_2n | 2 | 130 | 52 | 0 | 78 | 0.4000 | 1.0000 | 0.5714 | 0 |
| QuAcq (example-only) | arcade-game | rs_2n | 0 | 130 | 5 | 0 | 125 | 0.0385 | 1.0000 | 0.0741 | 0 |
| QuAcq (example-only) | arcade-game | rs_2n | 1 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| QuAcq (example-only) | arcade-game | rs_2n | 2 | 130 | 5 | 0 | 125 | 0.0385 | 1.0000 | 0.0741 | 0 |
| ConGen | arcade-game | rs_3n | 0 | 130 | 124 | 168 | 6 | 0.9538 | 0.4247 | 0.5877 | 0 |
| ConGen | arcade-game | rs_3n | 1 | 130 | 129 | 167 | 1 | 0.9923 | 0.4358 | 0.6056 | 0 |
| ConGen | arcade-game | rs_3n | 2 | 130 | 124 | 164 | 6 | 0.9538 | 0.4306 | 0.5933 | 0 |
| QuAcq (example-first) | arcade-game | rs_3n | 0 | 130 | 84 | 0 | 46 | 0.6462 | 1.0000 | 0.7850 | 0 |
| QuAcq (example-first) | arcade-game | rs_3n | 1 | 130 | 65 | 0 | 65 | 0.5000 | 1.0000 | 0.6667 | 0 |
| QuAcq (example-first) | arcade-game | rs_3n | 2 | 130 | 86 | 0 | 44 | 0.6615 | 1.0000 | 0.7963 | 0 |
| QuAcq (example-only) | arcade-game | rs_3n | 0 | 130 | 11 | 0 | 119 | 0.0846 | 1.0000 | 0.1560 | 0 |
| QuAcq (example-only) | arcade-game | rs_3n | 1 | 130 | 5 | 0 | 125 | 0.0385 | 1.0000 | 0.0741 | 0 |
| QuAcq (example-only) | arcade-game | rs_3n | 2 | 130 | 11 | 0 | 119 | 0.0846 | 1.0000 | 0.1560 | 0 |
| ConGen | arcade-game | rs_m | 0 | 130 | 130 | 127 | 0 | 1.0000 | 0.5058 | 0.6718 | 0 |
| ConGen | arcade-game | rs_m | 1 | 130 | 130 | 43 | 0 | 1.0000 | 0.7514 | 0.8581 | 0 |
| ConGen | arcade-game | rs_m | 2 | 130 | 130 | 33 | 0 | 1.0000 | 0.7975 | 0.8874 | 0 |
| QuAcq (example-first) | arcade-game | rs_m | 0 | 130 | 54 | 0 | 76 | 0.4154 | 1.0000 | 0.5870 | 0 |
| QuAcq (example-first) | arcade-game | rs_m | 1 | 130 | 42 | 0 | 88 | 0.3231 | 1.0000 | 0.4884 | 0 |
| QuAcq (example-first) | arcade-game | rs_m | 2 | 130 | 40 | 0 | 90 | 0.3077 | 1.0000 | 0.4706 | 0 |
| QuAcq (example-only) | arcade-game | rs_m | 0 | 130 | 3 | 0 | 127 | 0.0231 | 1.0000 | 0.0451 | 0 |
| QuAcq (example-only) | arcade-game | rs_m | 1 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| QuAcq (example-only) | arcade-game | rs_m | 2 | 130 | 4 | 0 | 126 | 0.0308 | 1.0000 | 0.0597 | 0 |
| ConGen | busybox-1.18.0 | 2cov | 0 | 994 | 994 | 3 | 0 | 1.0000 | 0.9970 | 0.9985 | 0 |
| ConGen | busybox-1.18.0 | 2cov | 1 | 994 | 994 | 7 | 0 | 1.0000 | 0.9930 | 0.9965 | 0 |
| ConGen | busybox-1.18.0 | 2cov | 2 | 994 | 994 | 7 | 0 | 1.0000 | 0.9930 | 0.9965 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | 2cov | 0 | 994 | 451 | 0 | 543 | 0.4537 | 1.0000 | 0.6242 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | 2cov | 1 | 994 | 461 | 0 | 533 | 0.4638 | 1.0000 | 0.6337 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | 2cov | 2 | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | 2cov | 0 | 994 | 446 | 0 | 548 | 0.4487 | 1.0000 | 0.6194 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | 2cov | 1 | 994 | 446 | 0 | 548 | 0.4487 | 1.0000 | 0.6194 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | 2cov | 2 | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 | 0 |
| ConGen | busybox-1.18.0 | ff | 0 | 994 | 994 | 189 | 0 | 1.0000 | 0.8402 | 0.9132 | 0 |
| ConGen | busybox-1.18.0 | ff | 1 | 994 | 994 | 260 | 0 | 1.0000 | 0.7927 | 0.8843 | 0 |
| ConGen | busybox-1.18.0 | ff | 2 | 994 | 994 | 285 | 0 | 1.0000 | 0.7772 | 0.8746 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | ff | 0 | 994 | 456 | 0 | 538 | 0.4588 | 1.0000 | 0.6290 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | ff | 1 | 994 | 460 | 0 | 534 | 0.4628 | 1.0000 | 0.6327 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | ff | 2 | 994 | 457 | 0 | 537 | 0.4598 | 1.0000 | 0.6299 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | ff | 0 | 994 | 446 | 0 | 548 | 0.4487 | 1.0000 | 0.6194 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | ff | 1 | 994 | 447 | 0 | 547 | 0.4497 | 1.0000 | 0.6204 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | ff | 2 | 994 | 447 | 0 | 547 | 0.4497 | 1.0000 | 0.6204 | 0 |
| ConGen | busybox-1.18.0 | rs_1n | 0 | 994 | 992 | 261 | 2 | 0.9980 | 0.7917 | 0.8830 | 0 |
| ConGen | busybox-1.18.0 | rs_1n | 1 | 994 | 993 | 240 | 1 | 0.9990 | 0.8054 | 0.8918 | 0 |
| ConGen | busybox-1.18.0 | rs_1n | 2 | 994 | 992 | 203 | 2 | 0.9980 | 0.8301 | 0.9063 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 0 | 994 | 459 | 0 | 535 | 0.4618 | 1.0000 | 0.6318 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 1 | 994 | 460 | 0 | 534 | 0.4628 | 1.0000 | 0.6327 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_1n | 2 | 994 | 464 | 0 | 530 | 0.4668 | 1.0000 | 0.6365 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 0 | 994 | 455 | 0 | 539 | 0.4577 | 1.0000 | 0.6280 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 1 | 994 | 452 | 0 | 542 | 0.4547 | 1.0000 | 0.6252 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_1n | 2 | 994 | 454 | 0 | 540 | 0.4567 | 1.0000 | 0.6271 | 0 |
| ConGen | busybox-1.18.0 | rs_m | 0 | 994 | 994 | 205 | 0 | 1.0000 | 0.8290 | 0.9065 | 0 |
| ConGen | busybox-1.18.0 | rs_m | 1 | 994 | 994 | 201 | 0 | 1.0000 | 0.8318 | 0.9082 | 0 |
| ConGen | busybox-1.18.0 | rs_m | 2 | 994 | 994 | 207 | 0 | 1.0000 | 0.8276 | 0.9057 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_m | 0 | 994 | 453 | 0 | 541 | 0.4557 | 1.0000 | 0.6261 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_m | 1 | 994 | 446 | 0 | 548 | 0.4487 | 1.0000 | 0.6194 | 0 |
| QuAcq (example-first) | busybox-1.18.0 | rs_m | 2 | 994 | 447 | 0 | 547 | 0.4497 | 1.0000 | 0.6204 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_m | 0 | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_m | 1 | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 | 0 |
| QuAcq (example-only) | busybox-1.18.0 | rs_m | 2 | 994 | 445 | 0 | 549 | 0.4477 | 1.0000 | 0.6185 | 0 |
| ConGen | fqa | 2cov | 0 | 342 | 342 | 109 | 0 | 1.0000 | 0.7583 | 0.8625 | 0 |
| ConGen | fqa | 2cov | 1 | 342 | 342 | 102 | 0 | 1.0000 | 0.7703 | 0.8702 | 0 |
| ConGen | fqa | 2cov | 2 | 342 | 342 | 104 | 0 | 1.0000 | 0.7668 | 0.8680 | 0 |
| QuAcq (example-first) | fqa | 2cov | 0 | 342 | 41 | 0 | 301 | 0.1199 | 1.0000 | 0.2141 | 0 |
| QuAcq (example-first) | fqa | 2cov | 1 | 342 | 14 | 0 | 328 | 0.0409 | 1.0000 | 0.0787 | 0 |
| QuAcq (example-first) | fqa | 2cov | 2 | 342 | 24 | 0 | 318 | 0.0702 | 1.0000 | 0.1311 | 0 |
| QuAcq (example-only) | fqa | 2cov | 0 | 342 | 8 | 0 | 334 | 0.0234 | 1.0000 | 0.0457 | 0 |
| QuAcq (example-only) | fqa | 2cov | 1 | 342 | 9 | 0 | 333 | 0.0263 | 1.0000 | 0.0513 | 0 |
| QuAcq (example-only) | fqa | 2cov | 2 | 342 | 9 | 0 | 333 | 0.0263 | 1.0000 | 0.0513 | 0 |
| ConGen | fqa | ff | 0 | 342 | 342 | 61 | 0 | 1.0000 | 0.8486 | 0.9181 | 0 |
| ConGen | fqa | ff | 1 | 342 | 342 | 58 | 0 | 1.0000 | 0.8550 | 0.9218 | 0 |
| ConGen | fqa | ff | 2 | 342 | 342 | 65 | 0 | 1.0000 | 0.8403 | 0.9132 | 0 |
| QuAcq (example-first) | fqa | ff | 0 | 342 | 22 | 0 | 320 | 0.0643 | 1.0000 | 0.1209 | 0 |
| QuAcq (example-first) | fqa | ff | 1 | 342 | 29 | 0 | 313 | 0.0848 | 1.0000 | 0.1563 | 0 |
| QuAcq (example-first) | fqa | ff | 2 | 342 | 63 | 0 | 279 | 0.1842 | 1.0000 | 0.3111 | 0 |
| QuAcq (example-only) | fqa | ff | 0 | 342 | 8 | 0 | 334 | 0.0234 | 1.0000 | 0.0457 | 0 |
| QuAcq (example-only) | fqa | ff | 1 | 342 | 8 | 0 | 334 | 0.0234 | 1.0000 | 0.0457 | 0 |
| QuAcq (example-only) | fqa | ff | 2 | 342 | 10 | 0 | 332 | 0.0292 | 1.0000 | 0.0568 | 0 |
| ConGen | fqa | rs_1n | 0 | 342 | 342 | 47 | 0 | 1.0000 | 0.8792 | 0.9357 | 0 |
| ConGen | fqa | rs_1n | 1 | 342 | 342 | 44 | 0 | 1.0000 | 0.8860 | 0.9396 | 0 |
| ConGen | fqa | rs_1n | 2 | 342 | 342 | 27 | 0 | 1.0000 | 0.9268 | 0.9620 | 0 |
| QuAcq (example-first) | fqa | rs_1n | 0 | 342 | 36 | 0 | 306 | 0.1053 | 1.0000 | 0.1905 | 0 |
| QuAcq (example-first) | fqa | rs_1n | 1 | 342 | 41 | 0 | 301 | 0.1199 | 1.0000 | 0.2141 | 0 |
| QuAcq (example-first) | fqa | rs_1n | 2 | 342 | 37 | 0 | 305 | 0.1082 | 1.0000 | 0.1953 | 0 |
| QuAcq (example-only) | fqa | rs_1n | 0 | 342 | 9 | 0 | 333 | 0.0263 | 1.0000 | 0.0513 | 0 |
| QuAcq (example-only) | fqa | rs_1n | 1 | 342 | 10 | 0 | 332 | 0.0292 | 1.0000 | 0.0568 | 0 |
| QuAcq (example-only) | fqa | rs_1n | 2 | 342 | 9 | 0 | 333 | 0.0263 | 1.0000 | 0.0513 | 0 |
| ConGen | fqa | rs_2n | 0 | 342 | 342 | 44 | 0 | 1.0000 | 0.8860 | 0.9396 | 0 |
| ConGen | fqa | rs_2n | 1 | 342 | 342 | 41 | 0 | 1.0000 | 0.8930 | 0.9434 | 0 |
| ConGen | fqa | rs_2n | 2 | 342 | 342 | 50 | 0 | 1.0000 | 0.8724 | 0.9319 | 0 |
| QuAcq (example-first) | fqa | rs_2n | 0 | 342 | 39 | 0 | 303 | 0.1140 | 1.0000 | 0.2047 | 0 |
| QuAcq (example-first) | fqa | rs_2n | 1 | 342 | 66 | 0 | 276 | 0.1930 | 1.0000 | 0.3235 | 0 |
| QuAcq (example-first) | fqa | rs_2n | 2 | 342 | 14 | 0 | 328 | 0.0409 | 1.0000 | 0.0787 | 0 |
| QuAcq (example-only) | fqa | rs_2n | 0 | 342 | 11 | 0 | 331 | 0.0322 | 1.0000 | 0.0623 | 0 |
| QuAcq (example-only) | fqa | rs_2n | 1 | 342 | 11 | 0 | 331 | 0.0322 | 1.0000 | 0.0623 | 0 |
| QuAcq (example-only) | fqa | rs_2n | 2 | 342 | 12 | 0 | 330 | 0.0351 | 1.0000 | 0.0678 | 0 |
| ConGen | fqa | rs_3n | 0 | 342 | 342 | 35 | 0 | 1.0000 | 0.9072 | 0.9513 | 0 |
| ConGen | fqa | rs_3n | 1 | 342 | 342 | 35 | 0 | 1.0000 | 0.9072 | 0.9513 | 0 |
| ConGen | fqa | rs_3n | 2 | 342 | 342 | 35 | 0 | 1.0000 | 0.9072 | 0.9513 | 0 |
| QuAcq (example-first) | fqa | rs_3n | 0 | 342 | 25 | 0 | 317 | 0.0731 | 1.0000 | 0.1362 | 0 |
| QuAcq (example-first) | fqa | rs_3n | 1 | 342 | 34 | 0 | 308 | 0.0994 | 1.0000 | 0.1809 | 0 |
| QuAcq (example-first) | fqa | rs_3n | 2 | 342 | 40 | 0 | 302 | 0.1170 | 1.0000 | 0.2094 | 0 |
| QuAcq (example-only) | fqa | rs_3n | 0 | 342 | 11 | 0 | 331 | 0.0322 | 1.0000 | 0.0623 | 0 |
| QuAcq (example-only) | fqa | rs_3n | 1 | 342 | 12 | 0 | 330 | 0.0351 | 1.0000 | 0.0678 | 0 |
| QuAcq (example-only) | fqa | rs_3n | 2 | 342 | 11 | 0 | 331 | 0.0322 | 1.0000 | 0.0623 | 0 |
| ConGen | fqa | rs_m | 0 | 342 | 342 | 41 | 0 | 1.0000 | 0.8930 | 0.9434 | 0 |
| ConGen | fqa | rs_m | 1 | 342 | 342 | 44 | 0 | 1.0000 | 0.8860 | 0.9396 | 0 |
| ConGen | fqa | rs_m | 2 | 342 | 342 | 49 | 0 | 1.0000 | 0.8747 | 0.9332 | 0 |
| QuAcq (example-first) | fqa | rs_m | 0 | 342 | 39 | 0 | 303 | 0.1140 | 1.0000 | 0.2047 | 0 |
| QuAcq (example-first) | fqa | rs_m | 1 | 342 | 27 | 0 | 315 | 0.0789 | 1.0000 | 0.1463 | 0 |
| QuAcq (example-first) | fqa | rs_m | 2 | 342 | 42 | 0 | 300 | 0.1228 | 1.0000 | 0.2188 | 0 |
| QuAcq (example-only) | fqa | rs_m | 0 | 342 | 6 | 0 | 336 | 0.0175 | 1.0000 | 0.0345 | 0 |
| QuAcq (example-only) | fqa | rs_m | 1 | 342 | 6 | 0 | 336 | 0.0175 | 1.0000 | 0.0345 | 0 |
| QuAcq (example-only) | fqa | rs_m | 2 | 342 | 6 | 0 | 336 | 0.0175 | 1.0000 | 0.0345 | 0 |

## Table: Strategy Eval (Description) on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.36/0.26/0.30 | 0.49/0.35/0.40 | 0.38/0.38/0.38 | 0.23/0.16/0.19 | 0.00/0.00/0.00 | 0.26/0.21/0.23 |
| KB2 | 0.89/0.69/0.78 | 0.89/0.67/0.76 | 0.91/0.68/0.78 | 0.79/0.74/0.76 | 0.42/0.41/0.41 | 0.81/0.69/0.74 |
| KB3 | 0.55/0.22/0.31 | 0.63/0.18/0.28 | 0.55/0.17/0.26 | 0.45/0.43/0.44 | 0.26/0.33/0.28 | 0.47/0.33/0.38 |
| KB4 | 0.66/0.60/0.63 | 0.71/0.63/0.67 | 0.72/0.67/0.69 | 0.58/0.58/0.58 | 0.31/0.42/0.32 | 0.58/0.56/0.57 |
| KB5 | 0.45/0.59/0.51 | n/a | n/a | 0.29/0.54/0.38 | 0.00/0.00/0.00 | 0.40/0.56/0.47 |

## Table: Strategy Eval (Clause) on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.76/0.66/0.71 | 0.83/0.72/0.77 | 0.74/0.81/0.77 | 0.55/0.51/0.52 | 0.09/0.20/0.13 | 0.61/0.59/0.60 |
| KB2 | 1.00/0.90/0.94 | 1.00/0.88/0.94 | 1.00/0.91/0.95 | 0.97/0.88/0.93 | 0.80/0.72/0.76 | 0.99/0.85/0.91 |
| KB3 | 0.77/0.43/0.55 | 0.80/0.35/0.49 | 0.77/0.35/0.48 | 0.72/0.60/0.65 | 0.44/0.60/0.48 | 0.74/0.50/0.59 |
| KB4 | 0.89/0.68/0.77 | 0.89/0.75/0.82 | 0.89/0.79/0.83 | 0.90/0.65/0.75 | 0.56/0.71/0.54 | 0.88/0.65/0.75 |
| KB5 | 0.53/0.67/0.59 | n/a | n/a | 0.49/0.69/0.58 | 0.00/0.30/0.01 | 0.52/0.66/0.58 |

## Table: Strategy Eval (Semantic) on Intersected KB — R/P/F1 - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 1.00/0.78/0.87 | 1.00/0.82/0.90 | 0.98/0.93/0.96 | 0.89/0.68/0.78 | 0.94/0.77/0.85 | 1.00/0.74/0.85 |
| KB2 | 1.00/0.90/0.95 | 1.00/0.88/0.94 | 1.00/0.91/0.95 | 1.00/0.88/0.94 | 1.00/0.77/0.87 | 1.00/0.85/0.92 |
| KB3 | 0.97/0.50/0.66 | 0.98/0.41/0.58 | 0.97/0.43/0.60 | 1.00/0.68/0.81 | 0.75/0.77/0.70 | 0.98/0.58/0.73 |
| KB4 | 0.97/0.70/0.82 | 1.00/0.78/0.88 | 1.00/0.81/0.90 | 1.00/0.67/0.80 | 1.00/0.87/0.93 | 1.00/0.68/0.81 |
| KB5 | 1.00/0.81/0.89 | n/a | n/a | 1.00/0.83/0.91 | 1.00/0.99/1.00 | 1.00/0.80/0.89 |

# Paper Tables (Non-incremental)

## Table 7: AcqMSS #consistency checks and runtime (msec) - Non-incremental Mode

| Strategy | |E+| | |E-| | KB1 | KB2 | KB3 | KB4 | KB5 |
|:---|---:|---:|:---:|:---:|:---:|:---:|:---:|
| RS(1n) | - | - | n/a | n/a | n/a | n/a | n/a |
| RS(2n) | - | - | n/a | n/a | n/a | n/a | n/a |
| RS(3n) | - | - | n/a | n/a | n/a | n/a | n/a |
| RS(m) | - | - | n/a | n/a | n/a | n/a | n/a |
| 2-COV | - | - | n/a | n/a | n/a | n/a | n/a |
| FF | - | - | n/a | n/a | n/a | n/a | n/a |

## Table 9: Accuracy with Random Sampling (RS) - Non-incremental Mode

| Strategy | KB1 | KB2 | KB3 | KB4 | KB5 |
|:---|:---:|:---:|:---:|:---:|:---:|
| RS(1n) | n/a | n/a | n/a | n/a | n/a |
| RS(2n) | n/a | n/a | n/a | n/a | n/a |
| RS(3n) | n/a | n/a | n/a | n/a | n/a |
| RS(m) | n/a | n/a | n/a | n/a | n/a |

## Table 10: Accuracy with 2-COV - Non-incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | - |
| KB2 | - |
| KB3 | - |
| KB4 | - |
| KB5 | - |

## Table 11: Accuracy with FF - Non-incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | - |
| KB2 | - |
| KB3 | - |
| KB4 | - |
| KB5 | - |

# Additional Tables (Non-incremental)

## Table: Fold Metrics (Precision / Recall / F1) - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB2 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB3 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB4 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB5 | n/a | n/a | n/a | n/a | n/a | n/a |

## Table: Accuracy (Compact) - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB2 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB3 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB4 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB5 | n/a | n/a | n/a | n/a | n/a | n/a |

## Table: Accuracy by Sampling Strategy - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB2 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB3 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB4 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB5 | n/a | n/a | n/a | n/a | n/a | n/a |

## Table: Runtime, mean [min–max over folds] - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB2 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB3 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB4 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB5 | n/a | n/a | n/a | n/a | n/a | n/a |

## Table: Consistency Checks - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB2 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB3 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB4 | n/a | n/a | n/a | n/a | n/a | n/a |
| KB5 | n/a | n/a | n/a | n/a | n/a | n/a |

## Table: Performance Metrics (Non-incremental)

| KB | Strategy | Runtime (ms) | #Checks | Memory (MB) | n_bias | n_mss | n_kb |
|:---|:---|---:|---:|---:|---:|---:|---:|

## Table: KB Summary (Non-incremental)

| KB | Strategy | n_bias | n_kb (mean) | n_intersected | Reduction |
|:---|:---|---:|---:|---:|---:|