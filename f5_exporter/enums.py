import enum

class NodeBalancingState(float, enum.Enum):
  OFFLINE: float = 0
  STAND_BY: float = 1
  ENABLED: float = 2
  OUT_OF_BALANCE: float = 3
  FORCED_DOWN: float = 4
