"""Shared helpers for the T11 oracle interaction-trace net (Layer 1).

Not a test module (no ``test_`` prefix) — imported by both the one-time fixture
recorder (``scripts/build_t11_oracle_net_fixtures.py``) and the replay test
(``tests/test_t11_oracle_trace_net.py``).

Anti-tautology contract:
- The golden VALUES live in committed JSON under ``fixtures/t11_oracle_net/``,
  recorded once from the CURRENT oracle. The replay test loads them; it never
  regenerates them.
- The frozen membership/completion queries also live in committed JSON. The
  query generators below run ONLY inside the recorder; the test loads the frozen
  list. Inputs regenerated at test time would make the trace a coincidence.
- ``canonical_snapshot`` is a pure normalizer shared by recorder and test so the
  two sides compare byte-identical JSON-native structures.
"""
import json
import random
from pathlib import Path

from tests.resource_paths import DATA_DIR

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "t11_oracle_net"

# One fixed probe seed for every FM.
_SEED = 20260712

# (name, uvl path, slow?, n_membership, m_completion). REAL-FM-7 fast, arcade the
# T5 ID anchor; busybox is the large FM (slow, excluded from the default gate) —
# fewer queries there since each is ~600 features wide, keeping the golden lean.
FM_SPECS = [
    ("REAL-FM-7", DATA_DIR / "fms" / "REAL-FM-7.uvl", False, 200, 20),
    ("arcade-game", DATA_DIR / "fms" / "arcade-game.uvl", False, 200, 20),
    ("busybox-1.18.0", DATA_DIR / "fms" / "busybox-1.18.0.uvl", True, 60, 6),
]


def _canon(obj):
    """Recursively normalize to a deterministic JSON-native structure.

    dict keys -> str (JSON has no int keys); tuple -> list; set -> sorted list.
    """
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_canon(v) for v in obj)
    return obj


def _canon_bgdata(bg):
    return {
        "set_kb": _canon(bg.set_kb),
        "assumptions": list(bg.assumptions),
        "negation_map": _canon(bg.negation_map),
        "descriptions": _canon(bg.descriptions),
        "next_available_id": bg.next_available_id,
        "assignment_clauses": _canon(bg.assignment_clauses),
        "assignment_assumptions": _canon(bg.assignment_assumptions),
        "pos_assignment_to_assumption": _canon(bg.pos_assignment_to_assumption),
        "neg_assignment_to_assumption": _canon(bg.neg_assignment_to_assumption),
    }


def canonical_snapshot(oracle):
    """Every observable getter on the oracle, taken BEFORE any query.

    get_c/get_kb/get_assumptions/get_bg_data are recorded pre-query so the
    golden never encodes the A6 last-query pollution of get_c (that behaviour
    is pinned separately, as an xfail, in the guard suite).
    """
    # NOTE: the dict keys below are LABELS of a frozen recording, not API names.
    # They do not move when a method is relocated — the golden JSON was recorded
    # under these labels, so keeping them keeps `git diff tests/fixtures/` empty.
    # Job ② (kb/assumptions/c/bg_data/root_clauses) moved off the live oracle onto
    # the frozen OracleData snapshot (ADR-0009); the values are byte-identical, so
    # the labels stay and the reads follow the data to its new home.
    #
    # The five FM-metadata labels (get_root_feature/get_cnf_clauses/
    # get_num_constraints/get_next_available_id/get_fm_data) were DROPPED with the
    # getters they recorded in the T11.4c API diet: a golden key may be dropped when
    # the API it records is deliberately deleted (that drop was the commit's purpose).
    # The retained labels below keep their exact recorded values.
    data = oracle.oracle_data
    return {
        "get_variables": sorted(oracle.get_variables()),
        "get_feature_ids": _canon(oracle.get_variable_ids()),
        "get_root_clauses": _canon(data.get_root_clauses()),
        "get_c": _canon(data.get_c()),
        "get_kb": _canon(data.get_kb()),
        "get_assumptions": _canon(data.get_assumptions()),
        "get_bg_data": _canon_bgdata(data.get_bg_data()),
    }


def replay_answers(oracle, queries):
    """Run the frozen queries and return the canonical answer trace.

    complete_configuration may return None (no valid completion) -> null.
    """
    membership = [oracle.is_valid(q) for q in queries["membership"]]
    completion = [
        _canon(oracle.complete_configuration(p)) for p in queries["completion"]
    ]
    return {"membership": membership, "completion": completion}


# --- recorder-only query generators (the replay test must NOT call these) ---
def build_frozen_queries(oracle, n_membership, m_completion):
    """Generate the frozen membership + completion query lists (recorder only).

    Random full assignments are almost always invalid, so the completions
    (guaranteed-valid full configs from complete_configuration) are appended to
    the membership list. That gives the golden genuine True answers — a broken
    is_valid that collapses to a constant would flip them and be caught. The
    resulting lists are committed to disk; the replay test only ever reads them.
    """
    feats = sorted(oracle.get_variables())
    rng = random.Random(_SEED)
    membership = [{f: rng.choice([True, False]) for f in feats}
                  for _ in range(n_membership)]
    completion = []
    for _ in range(m_completion):
        k = rng.randint(1, max(1, len(feats) // 2))
        chosen = sorted(rng.sample(feats, k))
        completion.append({f: rng.choice([True, False]) for f in chosen})

    valid_configs = [cfg for cfg in
                     (oracle.complete_configuration(p) for p in completion)
                     if cfg is not None]
    membership.extend(valid_configs)
    return {"membership": membership, "completion": completion}


def queries_path(name):
    return FIXTURES_DIR / f"queries_{name}.json"


def trace_path(name):
    return FIXTURES_DIR / f"trace_{name}.json"


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")
