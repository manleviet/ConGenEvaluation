#!/usr/bin/env python3
"""
Independent verification of a generated example-set + CV-fold bundle.

Falsification harness for a produced bundle. Reads only the produced JSON
files; imports nothing from the AcqMSS repo, so it cannot inherit a defect from
the code it is checking. Stdlib only.

    python3 tools/sosym_r1/verify_examples_bundle.py . [--model ea2468] [--seed 82] [--folds 3]

It passes clean on all five committed knowledge bases (REAL-FM-7, fqa,
arcade-game, REAL-FM-4, busybox-1.18.0), so it is calibrated against known-good
data and a failure means something. Re-run it on one of those first if you ever
doubt the harness rather than the bundle.

Exit 0 = every check passed. Exit 1 = at least one check failed.
"""

import argparse
import hashlib
import itertools
import json
import random
import sys
from datetime import datetime
from pathlib import Path

STRATEGIES = ["rs_1n", "rs_2n", "rs_3n", "rs_m", "2cov", "ff"]

failures: list[str] = []
notes: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(f"{label}{(' — ' + detail) if detail else ''}")
    return ok


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def expected_rs_split(total: int) -> tuple[int, int]:
    """Mirror of ControlledRandomSamplingGenerator.calculate_distribution
    with valid_configs absent."""
    n_neg = max(1, total // 10)
    return total - n_neg, n_neg


def generate_folds_reference(n_pos: int, n_neg: int, n_folds: int, seed: int) -> dict:
    """Byte-faithful reimplementation of conacq/eval/folds.py:generate_folds.
    Stdlib only, so it is independent of the repo."""
    rng = random.Random(seed)
    pos_idx = list(range(n_pos))
    neg_idx = list(range(n_neg))
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    pos_folds = [[] for _ in range(n_folds)]
    for i, idx in enumerate(pos_idx):
        pos_folds[i % n_folds].append(idx)
    neg_folds = [[] for _ in range(n_folds)]
    for i, idx in enumerate(neg_idx):
        neg_folds[i % n_folds].append(idx)
    shuffle_seeds = [rng.randint(0, 2 ** 31 - 1) for _ in range(n_folds)]
    return {
        "n_folds": n_folds,
        "seed": seed,
        "positive_folds": pos_folds,
        "negative_folds": neg_folds,
        "shuffle_seeds": shuffle_seeds,
    }


def verify_examples(path: Path, strategy: str, n_features: int, seed: int,
                    m_value: int | None) -> tuple[int, int]:
    print(f"\n== examples: {path.name} ==")
    if not path.exists():
        check(False, "file exists", str(path))
        return -1, -1
    data = json.loads(path.read_text())
    pos = data.get("positive", [])
    neg = data.get("negative", [])
    md = data.get("metadata", {})
    size = path.stat().st_size
    print(f"  |E+| = {len(pos)}  |E-| = {len(neg)}  "
          f"size = {size:,} B ({size / 1e6:.1f} MB)")
    print(f"  sha256 = {sha256(path)}")

    check(md.get("seed") == seed, "metadata.seed", f"got {md.get('seed')!r}")
    check(md.get("strategy") == strategy, "metadata.strategy",
          f"got {md.get('strategy')!r}")
    check(md.get("n_features") == n_features, "metadata.n_features",
          f"got {md.get('n_features')!r}")

    # Every assignment must be complete over the same feature set.
    all_ex = pos + neg
    if all_ex:
        keys = set(all_ex[0]["assignments"])
        check(len(keys) == n_features, "assignment width",
              f"{len(keys)} keys vs n_features {n_features}")
        ragged = [e["id"] for e in all_ex if set(e["assignments"]) != keys]
        check(not ragged, "all assignments share one feature set",
              f"{len(ragged)} ragged, first {ragged[:3]}")
        nonbool = [e["id"] for e in all_ex
                   if any(not isinstance(v, bool) for v in e["assignments"].values())]
        check(not nonbool, "all values boolean", f"{len(nonbool)} offenders")
        ids = [e["id"] for e in all_ex]
        check(len(set(ids)) == len(ids), "example ids unique",
              f"{len(ids) - len(set(ids))} duplicates")
        # Duplicate configurations are what the generator's dedup set exists to
        # prevent; a duplicate means the dedup did not hold.
        sigs = {tuple(sorted(e["assignments"].items())) for e in all_ex}
        check(len(sigs) == len(all_ex), "no duplicate configurations",
              f"{len(all_ex) - len(sigs)} duplicates")

    if strategy in ("rs_1n", "rs_2n", "rs_3n", "rs_m"):
        mult = {"rs_1n": 1, "rs_2n": 2, "rs_3n": 3}.get(strategy)
        total = n_features * mult if mult else m_value
        if total is None:
            notes.append(f"{strategy}: m unknown, split not checked")
        else:
            exp_p, exp_n = expected_rs_split(total)
            check(len(pos) == exp_p, f"{strategy} |E+|",
                  f"expected {exp_p}, got {len(pos)}")
            check(len(neg) == exp_n, f"{strategy} |E-|",
                  f"expected {exp_n}, got {len(neg)}")
            check(md.get("actual_positive") == len(pos)
                  and md.get("actual_negative") == len(neg),
                  "metadata counts agree with the arrays")

    if strategy == "2cov":
        total_comb = md.get("total_combinations")
        check(total_comb == len(pos) + len(neg), "total_combinations == |E+|+|E-|",
              f"{total_comb} vs {len(pos) + len(neg)}")
        verify_pairwise_coverage(all_ex, n_features)

    return len(pos), len(neg)


def verify_pairwise_coverage(examples: list, n_features: int) -> None:
    """The claim 'the 2-COV set is complete' is the one most likely to be an
    early stop reported as a success. Check it directly rather than trusting the
    generator: every unordered feature pair must show all four value pairs."""
    if not examples:
        check(False, "2-COV pairwise coverage", "no examples")
        return
    feats = sorted(examples[0]["assignments"])
    rows = [[e["assignments"][f] for f in feats] for e in examples]
    n = len(feats)
    total_pairs = n * (n - 1) // 2
    print(f"  checking all four value combinations on "
          f"C({n},2) = {total_pairs:,} feature pairs ...")
    # Column bitmasks: bit i set = row i has this feature True.
    true_mask = []
    for j in range(n):
        m = 0
        for i, row in enumerate(rows):
            if row[j]:
                m |= 1 << i
        true_mask.append(m)
    full = (1 << len(rows)) - 1
    false_mask = [full & ~m for m in true_mask]
    uncovered = 0
    first_bad = []
    for a, b in itertools.combinations(range(n), 2):
        ta, fa, tb, fb = true_mask[a], false_mask[a], true_mask[b], false_mask[b]
        if not (ta & tb) or not (ta & fb) or not (fa & tb) or not (fa & fb):
            uncovered += 1
            if len(first_bad) < 5:
                first_bad.append((feats[a], feats[b]))
    covered = total_pairs - uncovered
    pct = 100.0 * covered / total_pairs if total_pairs else 0.0
    check(uncovered == 0, "2-COV covers every feature pair",
          f"{covered:,}/{total_pairs:,} ({pct:.4f} %) — "
          f"{uncovered:,} uncovered, e.g. {first_bad}")


def verify_folds(path: Path, n_pos: int, n_neg: int, n_folds: int, seed: int) -> None:
    print(f"\n== folds: {path.name} ==")
    if not path.exists():
        check(False, "file exists", str(path))
        return
    data = json.loads(path.read_text())
    check(data.get("seed") == seed, "seed", f"got {data.get('seed')!r}")
    check(data.get("n_folds") == n_folds, "n_folds", f"got {data.get('n_folds')!r}")
    md = data.get("metadata", {})
    check(md.get("n_pos") == n_pos and md.get("n_neg") == n_neg,
          "metadata sizes match the example set",
          f"folds say {md.get('n_pos')}/{md.get('n_neg')}, examples say {n_pos}/{n_neg}")

    pf, nf = data.get("positive_folds", []), data.get("negative_folds", [])
    for label, folds, total in (("E+", pf, n_pos), ("E-", nf, n_neg)):
        flat = [i for f in folds for i in f]
        check(len(folds) == n_folds, f"{label}: {n_folds} folds", f"got {len(folds)}")
        check(sorted(flat) == list(range(total)), f"{label}: exact partition of 0..{total - 1}",
              f"{len(flat)} indices, {len(set(flat))} distinct, expected {total}")
        check(len(flat) == len(set(flat)), f"{label}: no index in two folds")
        if folds:
            sizes = [len(f) for f in folds]
            check(max(sizes) - min(sizes) <= 1, f"{label}: folds balanced", f"sizes {sizes}")
        # Leakage: the test fold and its train complement must be disjoint.
        for k in range(len(folds)):
            test = set(folds[k])
            train = set(i for j, f in enumerate(folds) if j != k for i in f)
            if test & train:
                check(False, f"{label}: fold {k} train/test leakage",
                      f"{len(test & train)} shared indices")
                break
        else:
            check(True, f"{label}: no train/test leakage in any fold")

    ref = generate_folds_reference(n_pos, n_neg, n_folds, seed)
    same = all(data.get(k) == ref[k] for k in
               ("n_folds", "seed", "positive_folds", "negative_folds", "shuffle_seeds"))
    check(same, "byte-identical to an independent reimplementation of generate_folds",
          "" if same else "the file was not produced by generate_folds(n_pos, n_neg, "
                          f"{n_folds}, {seed}) — check the seed and the example counts")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ap.add_argument("--model", default="ea2468")
    ap.add_argument("--n-features", type=int, default=None)
    ap.add_argument("--seed", type=int, default=82)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--strategies", nargs="*", default=STRATEGIES)
    args = ap.parse_args()

    ex_dir = args.repo / "data" / "examples"
    fold_dir = args.repo / "data" / "folds"

    n_features = args.n_features
    if n_features is None:
        for s in args.strategies:
            p = ex_dir / f"{args.model}_{s}.json"
            if p.exists():
                n_features = json.loads(p.read_text())["metadata"]["n_features"]
                break
    if n_features is None:
        print("no example file found; nothing to verify")
        return 1

    print(f"model {args.model} — n_features {n_features} — seed {args.seed} — "
          f"{args.folds} folds — {datetime.now().isoformat(timespec='seconds')}")

    # m comes from the 2-COV set, so read it first.
    m_value = None
    p2 = ex_dir / f"{args.model}_2cov.json"
    if p2.exists():
        d = json.loads(p2.read_text())
        m_value = len(d.get("positive", [])) + len(d.get("negative", []))
        print(f"m (2-COV count) = {m_value}")

    for s in args.strategies:
        n_pos, n_neg = verify_examples(
            ex_dir / f"{args.model}_{s}.json", s, n_features, args.seed, m_value)
        if n_pos >= 0:
            verify_folds(fold_dir / f"{args.model}_{s}_folds.json",
                         n_pos, n_neg, args.folds, args.seed)

    print("\n" + "=" * 70)
    for n in notes:
        print("note:", n)
    if failures:
        print(f"{len(failures)} FAILED CHECK(S):")
        for f in failures:
            print("  -", f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
