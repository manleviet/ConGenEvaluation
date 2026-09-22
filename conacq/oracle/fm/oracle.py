"""
Feature model oracle using SAT solver for validation.

Loads a feature model from .uvl file, converts to CNF, and validates
configurations via persistent PySAT solver.
"""

from typing import Dict, Optional, Set

from pysat.solvers import Solver

from conacq.oracle.fm.model import FMOracleModel
from conacq.oracle.fm.builder import FMOracleModelBuilder
from conacq.oracle.protocols import (
    MembershipOracle,
    CompletableOracle,
    CatalogProvider,
)
from explanation.api import variable_literals_to_config, config_to_assignment_assumptions
from explanation.api import build_checker, SolverBackend
from profiling import get_global_profiler, AbstractProfiler, measure_time, count_calls


class FMOracle(MembershipOracle, CompletableOracle, CatalogProvider):
    """Oracle using feature model as ground truth.

    Loads a feature model, converts it to CNF, and uses a SAT solver
    to validate configurations.

    Declares its three answer roles (ADR-0009/0010) by inheriting the narrow
    protocols: MembershipOracle (is_valid), CompletableOracle (complete_configuration),
    CatalogProvider (get_variables/get_variable_ids). Provisioning (job ②) is NOT a
    role of the oracle — it lives on the frozen OracleData snapshot.
    FM-specific methods: get_fm_data(), get_features(), etc.

    Example:
        >>> oracle = FMOracle('data/fms/model.uvl')
        >>> oracle.is_valid({'root': True, 'child': True})
        True
    """

    def __init__(self, fm_path: str, solver_name: str = 'glucose4',
                 use_incremental: bool = True,
                 profiler: AbstractProfiler = None):
        """Initialize oracle from feature model file.

        Args:
            fm_path: Path to feature model (.uvl format)
            solver_name: SAT solver name for checker
            profiler: Profiler instance (uses global if None)
        """
        self.fm_path = fm_path

        self.solver_name = solver_name
        self.profiler = profiler if profiler is not None else get_global_profiler()

        # Build the immutable FM KB, then RECEIVE the frozen provisioning snapshot
        # (job ②, ADR-0009) through the model's own facade — the same door the three
        # solve-task models use (model.prepare()), not a reach straight into the
        # strategy. The preparation assembles OracleData; the oracle does not build
        # what it provides, it only holds it.
        self._oracle_model = FMOracleModelBuilder.from_fm(fm_path).build()
        self.oracle_data = self._oracle_model.prepare()

        # The oracle builds its own membership checker (job ①) from the REAL task in
        # the snapshot (one source — no fabricated task). The oracle owns its solver
        # mode (use_incremental).
        self._checker = build_checker(
            self.oracle_data.task,
            SolverBackend.from_flags(use_incremental=use_incremental),
            solver_name, self.profiler)

        # Precompute the raw FM clauses once. constraint_map is immutable after
        # build, so this is a pure function of the KB (no solver state, no behaviour):
        # complete_configuration reuses it instead of rebuilding the list per call.
        self._fm_clauses = [
            clause for clauses in self._oracle_model.constraint_map.values()
            for clause in clauses]

    # --- Membership role (MembershipOracle) ---

    @measure_time('oracle_is_valid')
    @count_calls('oracle_is_valid_calls')
    def is_valid(self, assignments: Dict[str, bool]) -> bool:
        """Check if configuration is valid (satisfies FM constraints).

        Args:
            assignments: Feature assignments {feature_name: True/False}

        Returns:
            True if configuration is valid
        """
        # Read the catalog view once (not once per feature inside the generator).
        name_to_id = self._oracle_model.name_to_id
        if any(name not in name_to_id for name in assignments):
            raise KeyError(f"Unknown features in assignment: {set(assignments) - set(name_to_id)}")

        # COMPLETE assignment (covers every catalog feature): keep the exact prior behaviour.
        # For a full config, is_consistent(FM constraints + all-feature assumptions) ==
        # "no FM constraint is violated" == extension-SAT — the three coincide, so this path is
        # byte-identical for every complete-config caller (examples, generators, main query,
        # FindC discriminating configs). FM-constraint assumptions come from the immutable
        # OracleData's frozen set_c; the background handed to the checker cannot drift.
        if len(assignments) == len(name_to_id):
            set_c = list(self.oracle_data.task.set_c) + config_to_assignment_assumptions(
                assignments, self.oracle_data.assignment_map)
            return self._checker.is_consistent(set_c)

        # PARTIAL query (only FindScope, conacq/algorithms/quacq/findscope.py:64): the QuAcq
        # paper (Bessiere et al., IJCAI 2013) answers a partial query e_Y as NEGATIVE iff it
        # violates some target constraint whose scope ⊆ Y (all variables assigned). Constraints
        # with any unassigned variable are untestable and ignored. This is NOT extension-SAT:
        # extension-SAT over-rejects when the partial merely cannot be completed, which drove
        # FindScope's scope under-localisation (audit RC-1).
        return not self._partial_violates_fully_assigned_clause(assignments)

    def _partial_violates_fully_assigned_clause(self, assignments: Dict[str, bool]) -> bool:
        """Paper partial-query test: does the partial violate a target constraint whose
        variables are ALL assigned? Iterates the FM's raw CNF (self._fm_clauses, over feature
        ids — verified aux/Tseitin-free). A clause is *testable* iff every variable in it is
        assigned; it is *violated* iff all its literals are false. Returns True on the first
        violated testable clause (⇒ negative), False if none (⇒ positive)."""
        id_to_name = self._oracle_model.id_to_name
        for clause in self._fm_clauses:
            names = [id_to_name[abs(lit)] for lit in clause]
            if any(n not in assignments for n in names):
                continue  # not fully assigned ⇒ untestable ⇒ ignore
            # satisfied iff any literal is true: +id true when feature selected, -id when not
            if not any(assignments[n] if lit > 0 else not assignments[n]
                       for lit, n in zip(clause, names)):
                return True
        return False

    # --- Catalog role (CatalogProvider) ---

    def get_variables(self) -> Set[str]:
        """Get all feature names. The oracle exposes the catalog (CatalogProvider);
        the model owns the raw name↔id data."""
        return set(self._oracle_model.name_to_id.keys())

    def get_variable_ids(self) -> Dict[str, int]:
        """Get feature name → SAT variable ID mapping, derived from the model's
        name↔id catalog."""
        return dict(self._oracle_model.name_to_id)

    def complete_configuration(self, partial: Dict[str, bool]) -> Optional[Dict[str, bool]]:
        """Complete a partial configuration to a full valid one via SAT solving.

        If no valid completion exists for the given partial, falls back to
        returning any valid configuration (ignoring partial constraints).
        Returns None only if no valid configuration exists at all.

        Builds a FRESH solver per call, on raw FM clauses — deliberately NOT through
        ``self._checker`` (the membership port). This keeps completion a pure function
        of ``partial``: the returned witness is reproducible from its inputs alone and
        goes into a frozen dataset. Routing it through the (possibly persistent) port
        would make the witness depend on query history — a dataset migration, not a
        refactor (ADR-0011).

        Args:
            partial: Partial assignment {feature_name: True/False} for subset of features

        Returns:
            Full valid configuration dict, or None if no valid completion exists
        """
        assumptions = []
        for name, value in partial.items():
            fid = self._oracle_model.name_to_id[name]
            assumptions.append(fid if value else -fid)

        solver = Solver(name=self.solver_name)
        for clause in self._fm_clauses:
            solver.add_clause(clause)

        id_to_name = self._oracle_model.id_to_name
        try:
            if solver.solve(assumptions=assumptions):
                return variable_literals_to_config(solver.get_model(), id_to_name)
            # Fallback: try without assumptions
            if solver.solve():
                return variable_literals_to_config(solver.get_model(), id_to_name)
        finally:
            solver.delete()

        return None

    def __repr__(self):
        return f"FMOracle(features={len(self._oracle_model.name_to_id)})"

    def cleanup(self):
        """Release checker resources."""
        if hasattr(self, '_checker') and self._checker is not None:
            self._checker.cleanup()
            self._checker = None

    def __del__(self):
        self.cleanup()
