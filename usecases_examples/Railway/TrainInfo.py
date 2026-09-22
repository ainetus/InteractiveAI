"""
Train information and priority calculation.

Provides:
- TrainType: Enum for train categories
- TrainInfo: Train properties that affect priority
- calculate_priority(): Computes dynamic priority based on train properties

Priority factors:
- train_type: passenger > freight > maintenance
- passenger_count: More passengers = higher priority
- connection_frequency: Rare connections = higher priority (worse to miss)
- current_delay: Already-delayed trains get slight boost to prevent cascade
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class TrainType(Enum):
    """Train categories with base priority weights."""
    PASSENGER_EXPRESS = "passenger_express"
    PASSENGER_LOCAL = "passenger_local"
    FREIGHT = "freight"
    MAINTENANCE = "maintenance"


# Base priority weights by train type
TRAIN_TYPE_WEIGHTS: Dict[TrainType, float] = {
    TrainType.PASSENGER_EXPRESS: 1.5,
    TrainType.PASSENGER_LOCAL: 1.0,
    TrainType.FREIGHT: 0.3,
    TrainType.MAINTENANCE: 0.1,
}


@dataclass
class TrainInfo:
    """
    Information about a train that affects its priority.
    
    Attributes:
        train_id: Unique identifier
        train_type: Category (passenger, freight, etc.)
        passenger_count: Number of passengers (0 for freight)
        connection_frequency: Minutes between services on this route
            - 10 min = frequent service, missing one is not too bad
            - 60 min = rare service, missing one is very bad
        speed: Cells per timestep (1.0 = normal, 0.5 = slow freight)
        current_delay: Current delay in timesteps (for cascade prevention)
    """
    train_id: int
    train_type: TrainType = TrainType.PASSENGER_LOCAL
    passenger_count: int = 0
    connection_frequency: int = 10  # minutes between services
    speed: float = 1.0  # cells per timestep
    current_delay: int = 0  # current delay in timesteps
    
    # Optional descriptive name
    name: Optional[str] = None
    
    def __post_init__(self):
        if self.name is None:
            self.name = f"Train {self.train_id}"


def calculate_priority(train_info: TrainInfo) -> float:
    """
    Calculate dynamic priority for a train.
    
    Formula:
        priority = base_type × passenger_factor × connection_factor × delay_factor
    
    Where:
        - base_type: Weight from TRAIN_TYPE_WEIGHTS (1.5 for express, 0.3 for freight)
        - passenger_factor: 1.0 + (passengers / 500), range [1.0, 2.0+]
        - connection_factor: frequency / 10, higher = worse to miss
        - delay_factor: 1.0 + (delay / 60) × 0.5, slight boost for delayed trains
    
    Args:
        train_info: TrainInfo object with train properties
        
    Returns:
        Priority score (higher = more important to not delay)
    
    Examples:
        Express with 400 passengers, 30-min frequency, no delay:
            1.5 × 1.8 × 3.0 × 1.0 = 8.1
        
        Local with 50 passengers, 10-min frequency, 5-step delay:
            1.0 × 1.1 × 1.0 × 1.04 = 1.14
        
        Freight, no passengers, 120-min frequency, no delay:
            0.3 × 1.0 × 12.0 × 1.0 = 3.6
    """
    # Base weight from train type
    base = TRAIN_TYPE_WEIGHTS.get(train_info.train_type, 1.0)
    
    # Passenger factor: more passengers = higher priority
    # Range: 1.0 (empty) to 2.0+ (500+ passengers)
    passenger_factor = 1.0 + (train_info.passenger_count / 500)
    
    # Connection frequency factor: rare connections = higher priority
    # 10-min service: factor = 1.0
    # 60-min service: factor = 6.0 (6x worse to miss)
    connection_factor = train_info.connection_frequency / 10
    
    # Delay factor: slight boost for already-delayed trains to prevent cascade
    # No delay: factor = 1.0
    # 60-step delay: factor = 1.5
    delay_factor = 1.0 + (train_info.current_delay / 60) * 0.5
    
    return base * passenger_factor * connection_factor * delay_factor


def create_default_train_infos(n_trains: int) -> Dict[int, TrainInfo]:
    """
    Create default TrainInfo objects for testing.
    
    Train 0: Express passenger (high priority)
    Train 1: Local passenger (low priority)
    Additional trains: Freight
    """
    infos = {}
    
    if n_trains >= 1:
        infos[0] = TrainInfo(
            train_id=0,
            name="Express A",
            train_type=TrainType.PASSENGER_EXPRESS,
            passenger_count=300,
            connection_frequency=30,  # Every 30 min
            speed=1.0,
        )
    
    if n_trains >= 2:
        infos[1] = TrainInfo(
            train_id=1,
            name="Local B",
            train_type=TrainType.PASSENGER_LOCAL,
            passenger_count=50,
            connection_frequency=10,  # Every 10 min
            speed=1.0,
        )
    
    for i in range(2, n_trains):
        infos[i] = TrainInfo(
            train_id=i,
            name=f"Freight {i}",
            train_type=TrainType.FREIGHT,
            passenger_count=0,
            connection_frequency=120,  # Every 2 hours
            speed=0.5,  # Slower
        )
    
    return infos


# ============== PRIORITY COMPARISON HELPERS ==============

def compare_priorities(info_a: TrainInfo, info_b: TrainInfo) -> int:
    """
    Compare two trains by priority.
    
    Returns:
        1 if A has higher priority
        -1 if B has higher priority
        0 if equal
    """
    priority_a = calculate_priority(info_a)
    priority_b = calculate_priority(info_b)
    
    if priority_a > priority_b:
        return 1
    elif priority_b > priority_a:
        return -1
    else:
        return 0


def get_priority_explanation(train_info: TrainInfo) -> str:
    """
    Get human-readable explanation of priority calculation.
    
    Useful for debugging and future reasoning system.
    """
    base = TRAIN_TYPE_WEIGHTS.get(train_info.train_type, 1.0)
    passenger_factor = 1.0 + (train_info.passenger_count / 500)
    connection_factor = train_info.connection_frequency / 10
    delay_factor = 1.0 + (train_info.current_delay / 60) * 0.5
    total = base * passenger_factor * connection_factor * delay_factor
    
    lines = [
        f"Priority calculation for {train_info.name}:",
        f"  Base ({train_info.train_type.value}): {base:.2f}",
        f"  × Passenger factor ({train_info.passenger_count} pax): {passenger_factor:.2f}",
        f"  × Connection factor ({train_info.connection_frequency} min): {connection_factor:.2f}",
        f"  × Delay factor ({train_info.current_delay} steps late): {delay_factor:.2f}",
        f"  = Total priority: {total:.2f}",
    ]
    return "\n".join(lines)
