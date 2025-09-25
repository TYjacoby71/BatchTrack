from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BatchPortionSnapshot:
    is_portioned: bool
    portion_name: Optional[str]
    projected_portions: Optional[int]

