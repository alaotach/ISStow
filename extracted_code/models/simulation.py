from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class UsedItem(BaseModel):
    itemId: Optional[str] = None
    name: Optional[str] = None

class SimulationRequest(BaseModel):
    numOfDays: Optional[int] = None
    toTimestamp: Optional[str] = None  # ISO format
    itemsToBeUsedPerDay: List[UsedItem] = Field(default_factory=list)  # Empty list by default

class UsedItemResponse(BaseModel):
    itemId: str
    name: Optional[str] = None  # Make name optional
    remainingUses: Optional[int] = None  # Make remainingUses optional

class ExpiredItemResponse(BaseModel):
    itemId: str
    name: Optional[str] = None

class DepletedItemResponse(BaseModel):
    itemId: str
    name: Optional[str] = None

class SimulationChanges(BaseModel):
    itemsUsed: List[UsedItemResponse] = Field(default_factory=list)
    itemsExpired: List[ExpiredItemResponse] = Field(default_factory=list)
    itemsDepletedToday: List[DepletedItemResponse] = Field(default_factory=list)

class SimulationResponse(BaseModel):
    success: bool
    newDate: str  # ISO format
    changes: SimulationChanges