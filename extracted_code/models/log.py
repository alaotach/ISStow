from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class LogBase(BaseModel):
    timestamp: datetime
    userId: Optional[str] = None
    actionType: str  # "placement", "retrieval", "rearrangement", "disposal"
    itemId: str
    details: Dict[str, Any] = {}

class LogCreate(LogBase):
    pass

class LogInDB(LogBase):
    pass
    
    class Config:
        from_attributes = True

# This is the class that was missing
class LogEntry(LogBase):
    class Config:
        from_attributes = True

class LogResponse(BaseModel):
    logs: List[LogEntry] = []
    
    class Config:
        from_attributes = True

class LogQueryParams(BaseModel):
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    itemId: Optional[str] = None
    userId: Optional[str] = None
    actionType: Optional[str] = None