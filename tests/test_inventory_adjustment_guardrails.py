import re
from pathlib import Path

CANONICAL_ALLOWLIST = {
    # Known transitional modules that still perform manual adjustments and need refactors.
    "app/services/reservation_service.py",
    "app/services/pos_integration.py",
}


def test_no_direct_quantity_mutations_outside_canonical_service():
    root = Path("app")
    pattern = re.compile(r"\.quantity\s*([+\-]=)")
    violations = []

    for path in root.rglob("*.py"):
        rel_path = path.as_posix()
        if rel_path in CANONICAL_ALLOWLIST:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.start())
            if line_end == -1:
                line_end = len(text)
            line_text = text[line_start:line_end].strip()
            violations.append(f"{rel_path}: {line_text}")

    assert not violations, (
        "Direct quantity mutations detected outside the canonical inventory adjustment "
        "service. Review these call sites and route them through "
        "app.services.inventory_adjustment.process_inventory_adjustment: \n- "
        + "\n- ".join(violations)
    )
