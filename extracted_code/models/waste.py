from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.item import Position

class Location(BaseModel):
    module: Optional[str] = None
    position: Optional[str] = None

class WasteItem(BaseModel):
    itemId: str
    name: str
    reason: str  # "Expired", "Out of Uses", "Depleted"
    containerId: Optional[str] = None
    position: Optional[Any] = None  # Can be Position or dict
    weight: Optional[float] = None
    location: Optional[Location] = None
    disposalDate: Optional[str] = None

class WasteIdentifyResponse(BaseModel):
    success: bool
    wasteItems: List[Dict[str, Any]]

class UndockingRequest(BaseModel):
    maxWeight: float
    timestamp: str  # ISO format

class UndockingResponse(BaseModel):
    success: bool
    itemsRemoved: int
    totalWeight: float