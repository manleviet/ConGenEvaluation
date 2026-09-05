# Evaluation Results

Generated from: data/results/congen

KB Mapping: KB1=REAL-FM-7, KB2=fqa, KB3=arcade, KB4=REAL-FM-4


# Paper Tables (Incremental)

## Table 7: AcqMSS #consistency checks and runtime (msec) - Incremental Mode

| Strategy | |E+| | |E-| | KB1 | KB2 | KB3 | KB4 |
|:---|---:|---:|:---:|:---:|:---:|:---:|
| RS(1n) | 8 | 0 | 515 / 717.0 | 706 / 12227.9 | - | 3591 / 734895.0 |
| RS(2n) | 17 | 1 | 538 / 1500.1 | 713 / 34425.9 | - | - |
| RS(3n) | 25 | 2 | 544 / 2303.8 | 744 / 67511.8 | - | - |
| RS(m) | 5 | 0 | 466 / 425.4 | 476 / 840.8 | - | - |
| 2-COV | 0 | 6 | 10 / 113.2 | 10 / 1042.6 | - | - |
| FF | 4 | 2 | 452 / 355.4 | 622 / 3657.2 | - | - |

## Table 9: Accuracy with Random Sampling (RS) - Incremental Mode

| Strategy | KB1 | KB2 | KB3 | KB4 |
|:---|:---:|:---:|:---:|:---:|
| RS(1n) | 0.2778 ± 0.0481 | 0.8543 ± 0.0693 | - | 0.8243 ± 0.0742 |
| RS(2n) | 0.5583 ± 0.2184 | 0.9271 ± 0.0430 | - | - |
| RS(3n) | 0.8603 ± 0.1430 | 0.9665 ± 0.0057 | - | - |
| RS(m) | 0.1944 ± 0.1735 | 0.3667 ± 0.1528 | - | - |

## Table 10: Accuracy with 2-COV - Incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | 0.5556 ± 0.3849 |
| KB2 | 1.0000 ± 0.0000 |
| KB3 | - |
| KB4 | - |

## Table 11: Accuracy with FF - Incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | 0.4444 ± 0.1925 |
| KB2 | 0.7855 ± 0.0784 |
| KB3 | - |
| KB4 | - |

# Additional Tables (Incremental)

## Table: Fold Metrics (Precision / Recall / F1) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 1.00/0.23/0.38 | 1.00/0.53/0.68 | 1.00/0.85/0.91 | 0.33/0.11/0.17 | 0.00/0.00/0.00 | 0.33/0.17/0.22 |
| KB2 | 1.00/0.84/0.91 | 1.00/0.92/0.96 | 1.00/0.96/0.98 | 1.00/0.33/0.49 | 0.00/0.00/0.00 | 1.00/0.76/0.86 |
| KB3 | - | - | - | - | - | - |
| KB4 | 1.00/0.81/0.89 | - | - | - | - | - |

## Table: Accuracy (Compact) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.28±0.05 | 0.56±0.22 | 0.86±0.14 | 0.19±0.17 | 0.56±0.38 | 0.44±0.19 |
| KB2 | 0.85±0.07 | 0.93±0.04 | 0.97±0.01 | 0.37±0.15 | 1.00±0.00 | 0.79±0.08 |
| KB3 | - | - | - | - | - | - |
| KB4 | 0.82±0.07 | - | - | - | - | - |

## Table: Accuracy by Sampling Strategy - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.2778 ± 0.0481 | 0.5583 ± 0.2184 | 0.8603 ± 0.1430 | 0.1944 ± 0.1735 | 0.5556 ± 0.3849 | 0.4444 ± 0.1925 |
| KB2 | 0.8543 ± 0.0693 | 0.9271 ± 0.0430 | 0.9665 ± 0.0057 | 0.3667 ± 0.1528 | 1.0000 ± 0.0000 | 0.7855 ± 0.0784 |
| KB3 | - | - | - | - | - | - |
| KB4 | 0.8243 ± 0.0742 | - | - | - | - | - |

## Table: Runtime (ms) - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | 717 | 1.50s | 2.30s | 425 | 113 | 355 |
| KB2 | 12.23s | 34.43s | 67.51s | 841 | 1.04s | 3.66s |
| KB3 | - | - | - | - | - | - |
| KB4 | 734.89s | - | - | - | - | - |

## Table: Consistency Checks - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | 515 | 538 | 544 | 466 | 10 | 452 |
| KB2 | 706 | 713 | 744 | 476 | 10 | 622 |
| KB3 | - | - | - | - | - | - |
| KB4 | 3591 | - | - | - | - | - |

## Table: Performance Metrics (Incremental)

| KB | Strategy | Runtime (ms) | #Checks | Memory (MB) | n_bias | n_mss | n_kb |
|:---|:---|---:|---:|---:|---:|---:|---:|
| KB1 | RS(1n) | 716.98 ± 11.93 | 515 ± 10 | 0.48 | 295 | 91.7 | 16.7 |
| KB1 | RS(2n) | 1500.07 ± 67.83 | 538 ± 6 | 0.62 | 295 | 69.0 | 17.0 |
| KB1 | RS(3n) | 2303.76 ± 94.10 | 544 ± 7 | 0.77 | 295 | 61.7 | 12.3 |
| KB1 | RS(m) | 425.41 ± 53.37 | 466 ± 9 | 0.40 | 295 | 131.7 | 18.3 |
| KB1 | 2-COV | 113.24 ± 34.43 | 10 ± 0 | 0.33 | 295 | 294.0 | 4.0 |
| KB1 | FF | 355.40 ± 31.48 | 452 ± 22 | 0.40 | 295 | 142.3 | 19.0 |
| KB2 | RS(1n) | 12227.90 ± 79.33 | 706 ± 19 | 7.65 | 459 | 224.7 | 131.7 |
| KB2 | RS(2n) | 34425.86 ± 1599.23 | 713 ± 22 | 14.06 | 459 | 216.0 | 134.3 |
| KB2 | RS(3n) | 67511.82 ± 4049.30 | 744 ± 5 | 20.27 | 459 | 201.3 | 136.0 |
| KB2 | RS(m) | 840.79 ± 270.02 | 476 ± 29 | 1.84 | 459 | 344.3 | 108.7 |
| KB2 | 2-COV | 1042.63 ± 230.94 | 10 ± 0 | 1.46 | 459 | 458.0 | 106.0 |
| KB2 | FF | 3657.16 ± 319.90 | 622 ± 39 | 3.60 | 459 | 278.3 | 124.0 |
| KB4 | RS(1n) | 734894.96 ± 15193.12 | 3591 ± 101 | 30.82 | 2079 | 715.3 | 243.3 |

## Table: KB Summary (Incremental)

| KB | Strategy | n_bias | n_kb (mean) | n_intersected | Reduction |
|:---|:---|---:|---:|---:|---:|
| KB1 | RS(1n) | 295 | 16.7 | 6 | 94.4% |
| KB1 | RS(2n) | 295 | 17.0 | 12 | 94.2% |
| KB1 | RS(3n) | 295 | 12.3 | 9 | 95.8% |
| KB1 | RS(m) | 295 | 18.3 | 4 | 93.8% |
| KB1 | 2-COV | 295 | 4.0 | 3 | 98.6% |
| KB1 | FF | 295 | 19.0 | 3 | 93.6% |
| KB2 | RS(1n) | 459 | 131.7 | 103 | 71.3% |
| KB2 | RS(2n) | 459 | 134.3 | 110 | 70.7% |
| KB2 | RS(3n) | 459 | 136.0 | 122 | 70.4% |
| KB2 | RS(m) | 459 | 108.7 | 88 | 76.3% |
| KB2 | 2-COV | 459 | 106.0 | 105 | 76.9% |
| KB2 | FF | 459 | 124.0 | 98 | 73.0% |
| KB4 | RS(1n) | 2079 | 243.3 | 178 | 88.3% |

# Strategy Evaluation (Incremental)

## Table: Strategy Eval (Description) on Intersected KB - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.33/0.02/0.04 | 0.25/0.03/0.05 | 0.11/0.01/0.02 | 0.25/0.01/0.02 | 0.67/0.02/0.04 | 0.00/0.00/0.00 |
| KB2 | 0.83/0.84/0.84 | 0.75/0.81/0.78 | 0.73/0.87/0.79 | 0.83/0.72/0.77 | 0.33/0.34/0.34 | 0.80/0.76/0.78 |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Strategy Eval (Clause) on Intersected KB - Incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | 0.50/0.01/0.02 | 0.44/0.08/0.14 | 0.36/0.06/0.10 | 0.60/0.01/0.02 | 0.90/0.03/0.05 | 0.25/0.00/0.01 |
| KB2 | 0.97/0.93/0.95 | 0.94/0.91/0.93 | 0.93/0.96/0.94 | 0.93/0.88/0.90 | 0.74/0.69/0.71 | 0.88/0.95/0.91 |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

# Paper Tables (Non-incremental)

## Table 7: AcqMSS #consistency checks and runtime (msec) - Non-incremental Mode

| Strategy | |E+| | |E-| | KB1 | KB2 | KB3 | KB4 |
|:---|---:|---:|:---:|:---:|:---:|:---:|
| RS(1n) | - | - | - | - | - | - |
| RS(2n) | - | - | - | - | - | - |
| RS(3n) | - | - | - | - | - | - |
| RS(m) | - | - | - | - | - | - |
| 2-COV | - | - | - | - | - | - |
| FF | - | - | - | - | - | - |

## Table 9: Accuracy with Random Sampling (RS) - Non-incremental Mode

| Strategy | KB1 | KB2 | KB3 | KB4 |
|:---|:---:|:---:|:---:|:---:|
| RS(1n) | - | - | - | - |
| RS(2n) | - | - | - | - |
| RS(3n) | - | - | - | - |
| RS(m) | - | - | - | - |

## Table 10: Accuracy with 2-COV - Non-incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | - |
| KB2 | - |
| KB3 | - |
| KB4 | - |

## Table 11: Accuracy with FF - Non-incremental Mode

| KB | Accuracy |
|:---|:---:|
| KB1 | - |
| KB2 | - |
| KB3 | - |
| KB4 | - |

# Additional Tables (Non-incremental)

## Table: Fold Metrics (Precision / Recall / F1) - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | - | - | - | - | - | - |
| KB2 | - | - | - | - | - | - |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Accuracy (Compact) - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | - | - | - | - | - | - |
| KB2 | - | - | - | - | - | - |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Accuracy by Sampling Strategy - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| KB1 | - | - | - | - | - | - |
| KB2 | - | - | - | - | - | - |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Runtime (ms) - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | - | - | - | - | - | - |
| KB2 | - | - | - | - | - | - |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Consistency Checks - Non-incremental Mode

| KB | RS(1n) | RS(2n) | RS(3n) | RS(m) | 2-COV | FF |
|:---|---:|---:|---:|---:|---:|---:|
| KB1 | - | - | - | - | - | - |
| KB2 | - | - | - | - | - | - |
| KB3 | - | - | - | - | - | - |
| KB4 | - | - | - | - | - | - |

## Table: Performance Metrics (Non-incremental)

| KB | Strategy | Runtime (ms) | #Checks | Memory (MB) | n_bias | n_mss | n_kb |
|:---|:---|---:|---:|---:|---:|---:|---:|

## Table: KB Summary (Non-incremental)

| KB | Strategy | n_bias | n_kb (mean) | n_intersected | Reduction |
|:---|:---|---:|---:|---:|---:|