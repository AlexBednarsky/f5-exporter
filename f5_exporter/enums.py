import enum

class NodeBalancingState(float, enum.Enum):
  OFFLINE: float = 0
  USER_DISABLED: float = 1
  ENABLED: float = 2
