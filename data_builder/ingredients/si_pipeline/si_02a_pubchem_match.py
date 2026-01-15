"""SI Stage 2a — PubChem Stage 1 match (first pass).

Wrapper around `data_builder.ingredients.run_pre_ai_pipeline --stage pubchem_match`.
"""

from __future__ import annotations

import sys

from ._runner import build_stage_argv


def main(argv: list[str] | None = None) -> None:
    from data_builder.ingredients import run_pre_ai_pipeline

    run_pre_ai_pipeline.main(build_stage_argv("pubchem_match", argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    main()

