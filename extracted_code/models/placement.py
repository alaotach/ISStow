from pydantic import BaseModel
from typing import List, Optional
from models.item import Coordinates, Position

class PlacementBase(BaseModel):
    itemId: Optional[str] = None
    containerId: Optional[str] = None
    position: Optional[Position] = None

class PlacementCreate(PlacementBase):
    pass

class PlacementInDB(PlacementBase):
    pass
    
    class Config:
        from_attributes = True

class ItemPlacement(BaseModel):
    itemId: Optional[str] = None
    name: Optional[str] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None
    priority: Optional[int] = None
    expiryDate: Optional[str] = None
    usageLimit: Optional[int] = None
    preferredZone: Optional[str] = None
    allowNonPreferredZone: bool = True  # Allow placement in non-preferred zones by default

class ContainerPlacement(BaseModel):
    containerId: Optional[str] = None
    zone: Optional[str] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None

class PlacementRequest(BaseModel):
    items: List[ItemPlacement]
    containers: List[ContainerPlacement]

class PlacementResponse(BaseModel):
    success: bool
    placements: List[PlacementBase] = []
    unplaced_items: List[ItemPlacement] = []
    rearrangements: List = []

class RearrangementStep(BaseModel):
    step: Optional[int] = None
    action: Optional[str] = None  # "move", "remove", "place"
    itemId: Optional[str] = None
    fromContainer: Optional[str] = None
    fromPosition: Optional[Position] = None
    toContainer: Optional[str] = None
    toPosition: Optional[Position] = None
