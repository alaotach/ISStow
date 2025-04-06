from pydantic import BaseModel
from typing import List, Optional
from models.item import Coordinates, Position

class PlacementBase(BaseModel):
    itemId: str
    containerId: str
    position: Position

class PlacementCreate(PlacementBase):
    pass

class PlacementInDB(PlacementBase):
    pass
    
    class Config:
        from_attributes = True

class ItemPlacement(BaseModel):
    itemId: str
    name: str
    width: float
    depth: float
    height: float
    priority: int
    expiryDate: str
    usageLimit: int
    preferredZone: str
    allowNonPreferredZone: bool = True  # Allow placement in non-preferred zones by default

class ContainerPlacement(BaseModel):
    containerId: str
    zone: str
    width: float
    depth: float
    height: float

class PlacementRequest(BaseModel):
    items: List[ItemPlacement]
    containers: List[ContainerPlacement]

class PlacementResponse(BaseModel):
    success: bool
    placements: List[PlacementBase] = []
    unplaced_items: List[ItemPlacement] = []
    rearrangements: List = []

class RearrangementStep(BaseModel):
    step: int
    action: str  # "move", "remove", "place"
    itemId: str
    fromContainer: Optional[str] = None
    fromPosition: Optional[Position] = None
    toContainer: Optional[str] = None
    toPosition: Optional[Position] = None