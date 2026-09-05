"""Fluent builder for ConGenModel, mirroring QuAcqModelBuilder API.

The bias-load → negation-via-oracle skeleton lives in OracleBiasModelBuilder; this
builder only supplies the model-instance hook. The model it returns is a pure KB:
preparation (task + describe) is derived per run via
``model.prepare_task(ConGenTaskInput.from_examples(oracle_data, pos, neg))``, not
baked in at build time. Solver mode is the caller's, not the model's.
"""

from __future__ import annotations

from conacq.oracle_bias_model_builder import OracleBiasModelBuilder

from .congen_model import ConGenModel


class ConGenModelBuilder(OracleBiasModelBuilder[ConGenModel]):
    """Fluent builder for ConGenModel.

    Examples:
        oracle = FMOracle('data/fms/model.uvl')
        model = (ConGenModelBuilder
                 .from_bias('data/bias/model.json')
                 .with_oracle_data(oracle.oracle_data)
                 .build())  # pure KB; call model.prepare_task(...) to get a task
    """

    # === OracleBiasModelBuilder template hooks ===

    def _create_model_instance(self) -> ConGenModel:
        """Return a new, empty ConGenModel (bias KB filled by the base template)."""
        return ConGenModel()
