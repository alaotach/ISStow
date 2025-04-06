from fastapi import APIRouter, HTTPException, Query
from models.log import LogResponse, LogEntry
from database import logs_collection
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(
    prefix="/api",
    tags=["Logs"]
)

@router.get("/logs", response_model=LogResponse)
async def get_logs(
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    itemId: Optional[str] = Query(None),
    userId: Optional[str] = Query(None),
    actionType: Optional[str] = Query(None)
):
    """
    Retrieve logs based on filter criteria
    
    Parameters:
    - startDate: Start date for log range (ISO format)
    - endDate: End date for log range (ISO format)
    - itemId: Filter by item ID
    - userId: Filter by user ID
    - actionType: Filter by action type
    
    Returns: List of matching log entries
    """
    try:
        # Build query
        query = {}
        
        # Date range filter
        if startDate or endDate:
            query["timestamp"] = {}
            
            if startDate:
                try:
                    start_date = datetime.fromisoformat(startDate.replace('Z', '+00:00'))
                    query["timestamp"]["$gte"] = start_date
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid startDate format. Use ISO format (YYYY-MM-DDTHH:MM:SS).")
            
            if endDate:
                try:
                    end_date = datetime.fromisoformat(endDate.replace('Z', '+00:00'))
                    query["timestamp"]["$lte"] = end_date
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid endDate format. Use ISO format (YYYY-MM-DDTHH:MM:SS).")
        
        # Item ID filter
        if itemId:
            query["itemId"] = itemId
        
        # User ID filter
        if userId:
            query["userId"] = userId
        
        # Action type filter
        if actionType:
            valid_action_types = ["placement", "retrieval", "rearrangement", "disposal"]
            if actionType not in valid_action_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid actionType. Must be one of: {', '.join(valid_action_types)}"
                )
            query["actionType"] = actionType
        
        # Get logs from database
        logs_cursor = logs_collection.find(query).sort("timestamp", -1)
        logs = await logs_cursor.to_list(length=None)
        
        # Convert to response format
        log_entries = []
        for log in logs:
            # Ensure the timestamp is a datetime object
            if isinstance(log["timestamp"], str):
                try:
                    timestamp = datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00'))
                except ValueError:
                    timestamp = datetime.utcnow()  # Fallback if parsing fails
            else:
                timestamp = log["timestamp"]
                
            log_entries.append(LogEntry(
                timestamp=timestamp,
                userId=log.get("userId"),
                actionType=log["actionType"],
                itemId=log["itemId"],
                details=log.get("details", {})
            ))
        
        return LogResponse(logs=log_entries)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")