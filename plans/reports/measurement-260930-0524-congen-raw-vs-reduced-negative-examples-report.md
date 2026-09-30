# ConGen: does the result depend on minimizing the negative examples? (raw vs reduced NE)

Date 2026-09-30. Branch `feat/sosym-r1`. Frozen: `data/results_sosym_r1/`, ConGenEvaluation v1.0.0 (untouched; `git status` clean on the frozen tree after every step).

## What was done
- `[evaluation.congen] neg_mode = "reduced" | "raw"` (default reduced), wired run_cv → CV → ConGenRunner → ConGenModel.prepare_task → ConGenTaskPreparation → GenerateNE(minimize). The sibling prep subclass now hands `minimize` up via `super()`. Partials record the mode; resume refuses the other encoding's partials. Commit `68093ce`.
- Gate: default mode, REAL-FM-7 ff, one process per fold → identical to committed file on kb_constraints, redundant_constraints, ne_constraints, ne_clauses, redundant_ne_constraints, statistics, accuracy, metrics, and every consistency counter (timing fields ignored).
- Raw rerun of 27/28 combinations (81 folds), same folds/seed 42/glucose4/incremental/shuffle_bias, one process per fold, sequential, nothing else running. **busybox rs_1n: not rerun without minimization** (deadline; skipped via placeholder partials, removed after; no rs_1n fold was computed). Reduce replay for busybox rejected: B' AcqMss order is not stored (only the two Reduce subsequences), so no faithful replay exists.
- Scored with the Table 14 path: `make_score_configs.py --cv-dir` → `run_compare` (one block per file, own oracle).
- Scripts: `apps/sosym_r1/run_ne_raw_sweep.py`, `compare_ne_raw_vs_reduced.py`, `ne_theory_checks.py`, `score_with_retained_ne.py`, `summarize_ne_raw_vs_reduced.py`. Data + rendered tables: `data/results_sosym_r1_rawne/` (`summary.md` holds the full per-combination tables).

## Tests (red set)
Before (`a52a235`): 681 passed, 1 skipped, red set ∅. After (`9543647` code state): 686 passed, 1 skipped, red set ∅. +5 = `tests/test_congen_neg_mode.py` (mutation-checked: un-threading `minimize` turns it red). Env: Python 3.11.14, `../explanation` editable @ `8dd3b9e`, flamapy-fm/fw/sat 2.6.0.dev4.

## Verdicts (81 folds = 27 combinations)
| | result |
|---|---|
| P1 B' identical | **81/81** (set kb∪redundant; control \|B'\|=n_mss 81/81 both sides; AcqMss check count identical 81/81 ⇒ same recursion) |
| P2 KB identical where reduced n_ne=0 | **30/30** (ordered list equality) |
| P3 KB where reduced n_ne=1 | differs on **51/51**; raw n_ne = 0 on all 81 |
| P4 KB∪NE∪root rejects every training e⁻ | raw **81/81**, reduced incl. NE **81/81** (rebuild control reproduces recorded test accuracy 81/81 both sides) |
| Equivalence (KB_red ∪ NE_red ∪ root) ≡ (KB_raw ∪ root) | **equivalent 81/81**; reduced-stronger 0, raw-stronger 0, incomparable 0 (no witness exists). Negative controls: root removed from raw → reduced_stronger, witness `NOT(jplug = false)`; one constraint removed from reduced → raw_stronger, witness `c188` |
| Test-fold accuracy | identical on 81/81 folds (follows from equivalence) |

Why KBs differ (5,708 differing constraints over 51 folds, classified by SAT in Reduce's view, BG empty): 5,627 kept only by raw and entailed by reduced's bias KB **only once its retained ¬e⁻ is added** ("ne"); 81 are representative/order swaps ("order", entailed by the other bias KB alone; 64 of them are reduced-only); 0 "absent". Retained reduced ¬e⁻: 51 facts, 12 distinct, all "NOT(f = false)" units except two binary ones (`StationarySprite = false & Velocity = false`, `mdi = false & sdi = false`); equal to the root axiom on 26 folds. Mechanism: Reduce assembles NE first; a surviving unit fact makes every B' constraint it entails redundant; raw ¬e⁻ are entailed by B' and all discharge, replacing nothing. The retained fact follows from KB_raw ∪ root on every fold, hence equivalence.

## Printed cells that change (raw vs committed reduced; 27 combinations)
- Table 13 accuracy: **0**.
- Tables 11/13 |KB|: **18** (unchanged: REAL-FM-4 rs_m, REAL-FM-7 rs_1n/rs_2n, all 6 fqa). Largest: busybox 2cov 6.7→840.7, busybox ff 647.3→1,039.0, busybox rs_m 484.7→879.0, REAL-FM-4 2cov 138.0→212.7.
- Table 14 semantic: F1 **14**, P 13, R 9. Raw R = 1.000 on all 27. Largest F1 moves: busybox 2cov 0.997→0.833, arcade 2cov 0.705→0.807, REAL-FM-4 2cov 0.930→0.866, REAL-FM-7 rs_m 0.775→0.832.
- Table 12 clause F1 **18**, description F1 **18** (mostly up under raw: busybox 2cov clause 0.005→0.752, desc 0.000→0.466).
- Table 9: GenerateNE checks 27/27 (→ 0), total checks 27/27, runtime 27/27. Runtime deltas include run-to-run/day noise (the reduced runs are the committed sweep, measured on other days); only the check counts are deterministic.
- Full per-combination values: `data/results_sosym_r1_rawne/summary.md`.

## Scoring variant: reduced WITH retained NE (report only; no generator changed)
- Semantic/clause: exactly the scorer's code paths with the ¬e⁻ clauses appended. Control: excluded variant reproduces stored evaluation on 84/84 reduced and 81/81 raw folds.
- Semantic F1 red-excl → red+NE differs on 14 folds; red+NE recall = 1.000 on every combination. Where reduced recall < 1 (9 cells), including the NE restores R to 1.000 (= raw) in all 9, and F1 equals raw at printed precision in 7/9 (e.g. REAL-FM-7 rs_m 0.775 / 0.832 / 0.832). The 2 exceptions differ through P only: REAL-FM-7 2cov 0.849 / 0.881 / 0.806, arcade 2cov 0.705 / 0.904 / 0.807. Precision can still differ between red+NE and raw on equivalent theories: the semantic P proxy counts unentailed KB **clauses**, so it depends on the representation, not only the theory (busybox 2cov P 0.994 vs 0.714).
- Description strategy cannot match a ¬e⁻: the scorer keys on bias descriptions and a ¬e⁻ has no bias id, so it is skipped (red+NE = red-excl exactly). Forced into the acquired set, its "NOT(f = false)" string equals a target description on **0/84** folds, i.e. it can only add an FP (e.g. REAL-FM-7 ff fold 0 desc F1 0.207 → 0.200).
- busybox rs_1n (reduced only): red-excl = red+NE (sem F1 0.894).

## Compactness (|KB| + n_ne)
Total 12,509 reduced vs 18,038 raw over 81 folds; reduced smaller on 51/51 folds with a retained ¬e⁻, equal on the other 30. Relative reduction on those 51: min 0.008, median 0.103, max 0.994. Extreme: busybox 2cov fold 0, 4+1 vs 842+0. Per combination: 0.991 (busybox 2cov) … 0 (all fqa, REAL-FM-4 rs_m, REAL-FM-7 rs_1n/rs_2n).

## GenerateNE checks saved
Per fold min 0, median 67, max 748; per combination mean 5 (arcade rs_m) … 745 (REAL-FM-4 rs_3n). Raw: 0 on every fold, no oracle call.

## Against the interim reading
- Confirmed: P1, P2, identical accuracy, raw n_ne = 0, reduced smaller on every n_ne=1 fold, unit-fact mechanism, NE-first order.
- Counts moved with the full data: 51 n_ne=1 folds among the 81 rerun (54/84 incl. busybox rs_1n); totals 12,509 vs 18,038; extreme is busybox 2cov fold 0 (5 vs 842), not REAL-FM-4 2cov fold 0.
- **Falsified**: "reduced theory may be strictly stronger". Equivalent on 81/81; the retained fact is entailed by KB_raw ∪ root on every fold.

## Provenance
Sweep folds ran at `1b29b8b` (54) and `6b3ab6b` (27); the two differ only in the comparison script, not in any code the runs execute. Ledger: `data/results_sosym_r1_rawne/run-ledger.jsonl` (81 rows, 3.9 h wall). Commits: `68093ce` switch+test, `1b29b8b`/`6b3ab6b`/`9543647` scripts, `f8623ae` data.

## Unresolved
- Runtime comparison is cross-day; a like-for-like timing would need reduced rerun in the same window.
- busybox rs_1n not rerun (≈12.6 h); its P1–P4/equivalence are unmeasured.
