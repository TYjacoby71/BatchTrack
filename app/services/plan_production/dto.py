from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PortioningPlan:
    is_portioned: bool
    portion_name: Optional[str] = None
    portion_count: Optional[int] = None
    portion_unit_id: Optional[int] = None
    portion_unit_name: Optional[str] = None


@dataclass(frozen=True)
class ContainerSelection:
    id: int
    quantity: int


@dataclass(frozen=True)
class StartBatchRequest:
    recipe_id: int
    scale: float
    batch_type: str
    notes: str
    requires_containers: bool
    containers: List[ContainerSelection]
    portioning: Optional[PortioningPlan]
    projected_yield: Optional[float] = None
    projected_yield_unit: Optional[str] = None
