"""
Standalone SAT utility functions for QuAcq algorithm.

Pure functions extracted from QuAcqTask — shared by FindScope, FindC,
DiscriminatingGenerator, and QuAcq.learn().
"""

from explanation.api import config_to_assignment_assumptions
from profiling import count_calls, get_global_profiler


@count_calls('prune_calls')
def prune_rejecting(
        checker,
        assignment_map,
        remaining_bias: dict,
        assignment: dict,
        root_assumption: int,
        profiler=None,
        include_bg: bool = True
) -> list:
    """Remove constraints from remaining_bias that reject the given assignment.

    ``include_bg=True`` (default — COMPLETE-assignment callers, e.g. the main loop): a constraint
    is pruned if root(BG) + assignment + constraint is UNSAT. Sound because a complete positive
    assignment already satisfies BG, so BG cannot flip the verdict.

    ``include_bg=False`` (PARTIAL-assignment callers, e.g. FindScope): drop root, so a constraint
    is pruned ONLY when the partial assignment fully assigns and falsifies one of its clauses
    (``assignment + constraint`` UNSAT without BG ⟺ some clause of the constraint has all literals
    fixed-false by the partial). This is the paper's fully-assigned-clause rule; with BG the check
    is extension-SAT and wrongly condemns FM-entailed candidates whose scope the partial does not
    fully assign (the same defect class as the is_valid fix, at a second call site).

    Stateless: the assignment→assumption map is passed in (from the prepared task),
    not read from a live model.

    Returns list of pruned constraint assumption IDs.
    Mutates remaining_bias in-place.
    """
    if profiler is None:
        profiler = get_global_profiler()
    config_assumptions = config_to_assignment_assumptions(assignment, assignment_map)
    base = ([root_assumption] if include_bg else []) + config_assumptions
    pruned = []
    for c_id in list(remaining_bias):
        profiler.increment('prune_is_consistent_calls')
        if not checker.is_consistent(base + [c_id]):
            pruned.append(c_id)
    for c_id in pruned:
        remaining_bias.pop(c_id, None)
    if pruned:  # diagnostic counters: constraints pruned, split by call site (sound vs paper-faithful)
        profiler.increment('quacq_prune_complete_pruned' if include_bg else 'quacq_prune_partial_pruned',
                           len(pruned))
    return pruned
