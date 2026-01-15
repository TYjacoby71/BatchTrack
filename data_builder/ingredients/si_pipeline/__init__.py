"""Numbered wrappers for the deterministic pre-AI pipeline.

These modules exist purely to make the intended run order obvious in-repo.
They call `data_builder.ingredients.run_pre_ai_pipeline` with a fixed `--stage`.
"""

__all__ = [
    "si_01_ingest",
    "si_02a_pubchem_match",
    "si_02b_pubchem_retry",
    "si_03_pubchem_fetch",
    "si_04_pubchem_apply",
]

