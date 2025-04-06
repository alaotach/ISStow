from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class ItemBase(BaseModel):
    itemId: str
    name: str
    width: float
    depth: float
    height: float
    priority: int
    expiryDate: str  # ISO format date string
    usageLimit: int
    preferredZone: str
    allowNonPreferredZone: bool = True  # Default to allowing placement in non-preferred zones
    
class ItemCreate(ItemBase):
    pass

class ItemInDB(ItemBase):
    currentUses: int = 0
    isWaste: bool = False
    wasteReason: Optional[str] = None
    isPlaced: bool = False
    actualZone: Optional[str] = None
    
    class Config:
        from_attributes = True

class ItemResponse(ItemBase):
    currentUses: int
    isWaste: bool
    wasteReason: Optional[str]
    isPlaced: bool
    actualZone: Optional[str]
    containerName: Optional[str]  # Add containerName field
    position: Optional[Dict[str, Any]]  # Add position field
    
    class Config:
        from_attributes = True

class Coordinates(BaseModel):
    width: float
    depth: float
    height: float

class Position(BaseModel):
    startCoordinates: Coordinates
    endCoordinates: Coordinates

# Import/Export related models
class ImportError(BaseModel):
    row: Union[int, str]
    message: str

class ItemsImportResponse(BaseModel):
    success: bool
    itemsImported: int
    errors: List[ImportError] = []