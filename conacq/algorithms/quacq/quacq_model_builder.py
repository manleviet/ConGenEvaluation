"""Fluent builder for QuAcqModel, mirroring ConGenModelBuilder API.

The bias-load → negation-via-oracle skeleton lives in OracleBiasModelBuilder;
this builder only supplies the model-instance hook. The model it returns is a pure
KB: preparation (task + assignment map) is derived per run via
``model.prepare_task(QuAcqTaskInput(oracle_data))``, not baked in at build time.
"""

from __future__ import annotations

from conacq.oracle_bias_model_builder import OracleBiasModelBuilder

from .quacq_model import QuAcqModel


class QuAcqModelBuilder(OracleBiasModelBuilder[QuAcqModel]):
    """Fluent builder for QuAcqModel.

    Examples:
        oracle = FMOracle('data/fms/model.uvl')
        model = (QuAcqModelBuilder
                 .from_bias('data/bias/model.json')
                 .with_oracle_data(oracle.oracle_data)
                 .build())  # pure KB; call model.prepare_task(...) to get a task
    """

    # === OracleBiasModelBuilder template hooks ===

    def _create_model_instance(self) -> QuAcqModel:
        """Return a new, empty QuAcqModel (bias KB filled by the base template)."""
        return QuAcqModel()
