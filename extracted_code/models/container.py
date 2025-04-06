from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

class ContainerBase(BaseModel):
    containerId: str
    zone: str
    width: float
    depth: float
    height: float

class ContainerCreate(ContainerBase):
    pass

class ContainerInDB(ContainerBase):
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ContainerResponse(ContainerBase):
    class Config:
        from_attributes = True

# Import/Export related models
class ImportError(BaseModel):
    row: Union[int, str]
    message: str

class ContainersImportResponse(BaseModel):
    success: bool
    containersImported: int
    errors: List[ImportError] = []

class ContainerPlacement(BaseModel):
    containerId: str
    zone: str
    width: float
    depth: float
    height: float