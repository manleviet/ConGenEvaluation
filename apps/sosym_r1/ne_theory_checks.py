"""Logical checks on a raw/reduced pair of ConGen folds, read from their fold records.

The delivered theory of a fold is its bias KB (kb_constraints, via the bias's CNF) plus
its retained ¬e⁻ (ne_clauses, over feature variables) plus the root axiom (bg_clauses).
Every check here is a SAT entailment over those clauses; nothing is inferred from
constraint names or descriptions.
"""

from __future__ import annotations

from pathlib import Path

from pysat.solvers import Solver

from conacq.eval import apply_folds, load_folds
from conacq.eval.accuracy import AccuracyCalculator
from conacq.examples import ExampleIO

REPO = Path(__file__).resolve().parents[2]


def ids(entries):
    return [c['id'] if isinstance(c, dict) else c for c in entries]


def entails(theory: list, clauses: list) -> bool:
    """theory |= every clause: theory AND NOT(clause) is UNSAT for each one."""
    with Solver(name='glucose4', bootstrap_with=theory) as sat:
        return not any(sat.solve(assumptions=[-lit for lit in cl]) for cl in clauses)


def explain_difference(model_kb, fr: dict, fd: dict) -> dict:
    """Why the two KBs differ, by entailment rather than by narrative.

    Reduce's BG is EMPTY for a feature model: the root is kept out of acquisition and
    re-added at delivery. So a constraint one side kept and the other dropped is
    classified against the OTHER side, in Reduce's own view first (no root):

      order    entailed by the other bias KB alone -- another representative of the
               same theory was kept (Reduce is order-dependent)
      ne       entailed only once the other side's surviving ¬e⁻ is added -- Reduce
               dropped it because that memorized fact entails it
      root     entailed only once the root axiom is also added (not a reason Reduce
               could have used; the delivered theories still agree on it)
      absent   not entailed even by the other delivered theory -- a semantic change

    Also: whether each delivered theory (bias + ¬e⁻ + root) entails the other, and
    whether each side's surviving ¬e⁻ is literally the root axiom."""
    def bias(fold):
        return [list(c) for cid in ids(fold['kb_constraints'])
                for c in model_kb.constraint_map.get(cid, ())]

    def ne(fold):
        return [list(c) for c in fold['ne_clauses']]

    def root(fold):
        return [list(c) for c in fold['bg_clauses']]

    def why(cid, other):
        cl = [list(c) for c in model_kb.constraint_map[cid]]
        if entails(bias(other), cl):
            return 'order'
        if entails(bias(other) + ne(other), cl):
            return 'ne'
        if entails(bias(other) + ne(other) + root(other), cl):
            return 'root'
        return 'absent'

    kb_r, kb_d = ids(fr['kb_constraints']), ids(fd['kb_constraints'])
    delivered = lambda f: bias(f) + ne(f) + root(f)  # noqa: E731
    return {'only_raw_why': {c: why(c, fd) for c in kb_r if c not in kb_d},
            'only_reduced_why': {c: why(c, fr) for c in kb_d if c not in kb_r},
            'raw_entails_reduced': entails(delivered(fr), delivered(fd)),
            'reduced_entails_raw': entails(delivered(fd), delivered(fr)),
            'ne_is_root_raw': bool(ne(fr)) and all(c in root(fr) for c in ne(fr)),
            'ne_is_root_reduced': bool(ne(fd)) and all(c in root(fd) for c in ne(fd))}


def rejects_training_negatives(stem, model, fold, model_kb) -> tuple[bool, bool, int]:
    """(control_ok, all training e⁻ rejected, #training e⁻) for one fold, its
    retained ¬e⁻ included. control_ok = the rebuilt theory reproduces the fold's
    recorded test accuracy; nothing is claimed from a fold that fails it."""
    ex = ExampleIO.load_json(str(REPO / 'data' / 'examples' / f'{model}.json'))
    pos = [e.assignments for e in ex.positive]
    neg = [e.assignments for e in ex.negative]
    fd = load_folds(str(REPO / 'data' / 'folds' / f'{model}_folds.json'))
    _, tr_neg, te_pos, te_neg = apply_folds(fd, pos, neg, fold['fold_index'])
    theory = ([list(c) for cid in ids(fold['kb_constraints'])
               for c in model_kb.constraint_map.get(cid, ())]
              + [list(c) for c in fold['ne_clauses']] + [list(c) for c in fold['bg_clauses']])
    with AccuracyCalculator(theory, model_kb.name_to_id, 'glucose4') as calc:
        control = abs(calc.calculate(te_pos, te_neg).metrics.accuracy
                      - fold['accuracy']) < 1e-9
        m = calc.calculate([], tr_neg).metrics
    return control, m.false_positives == 0, len(tr_neg)


def _parts(model_kb, fold) -> list:
    """(label, clauses) per element of the delivered theory: each bias constraint,
    each retained ¬e⁻, and the root. The unit a witness is named in."""
    desc = {c['id']: c['description'] for c in fold['kb_constraints'] if isinstance(c, dict)}
    parts = [(f"{cid}: {desc.get(cid, '')}",
              [list(c) for c in model_kb.constraint_map.get(cid, ())])
             for cid in ids(fold['kb_constraints'])]
    names = fold.get('ne_constraints') or []
    parts += [(names[i] if i < len(names) else f'ne[{i}]', [list(c)])
              for i, c in enumerate(fold['ne_clauses'])]
    return parts + [('root', [list(c) for c in fold['bg_clauses']])]


def equivalence(model_kb, fr: dict, fd: dict) -> dict:
    """(KB_red ∪ NE_red ∪ BG) vs (KB_raw ∪ NE_raw ∪ BG), both directions, by SAT.

    On a failed direction, the witness is the FIRST element of the entailed side (in
    its KB order) that the other theory does not entail."""
    raw, red = _parts(model_kb, fr), _parts(model_kb, fd)
    t_raw = [c for _, cl in raw for c in cl]
    t_red = [c for _, cl in red for c in cl]

    def witness(theory, parts):
        with Solver(name='glucose4', bootstrap_with=theory) as sat:
            for label, cl in parts:
                if any(sat.solve(assumptions=[-lit for lit in c]) for c in cl):
                    return label
        return None
    w_red = witness(t_raw, red)     # a reduced element raw does NOT entail
    w_raw = witness(t_red, raw)     # a raw element reduced does NOT entail
    verdict = {(None, None): 'equivalent', (None, 'x'): 'raw_stronger',
               ('x', None): 'reduced_stronger', ('x', 'x'): 'incomparable'}[
        (w_red and 'x', w_raw and 'x')]
    return {'verdict': verdict, 'raw_misses_from_reduced': w_red,
            'reduced_misses_from_raw': w_raw}
