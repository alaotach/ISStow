from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict, Any
from datetime import datetime
import copy

from models.waste import (
    WasteItem, 
    WasteIdentifyResponse,
    UndockingRequest,
    UndockingResponse
)
from services.waste import (
    identify_waste_items,
    undock_items_with_weight_limit,
    complete_undocking_expired_items
)

router = APIRouter(prefix="/api/waste", tags=["Waste Management"])

@router.get("/identify", response_model=WasteIdentifyResponse)
async def identify_waste():
    """
    Identify items that should be considered waste (expired or used up)
    """
    waste_items = await identify_waste_items()
    
    # Convert to response format
    waste_items_response = []
    for item in waste_items:
        position_data = None
        if item.position:
            try:
                # Handle both Pydantic models and dictionaries
                if hasattr(item.position, 'startCoordinates') and hasattr(item.position, 'endCoordinates'):
                    # It's a Pydantic model
                    position_data = {
                        "startCoordinates": {
                            "width": item.position.startCoordinates.width,
                            "depth": item.position.startCoordinates.depth,
                            "height": item.position.startCoordinates.height
                        },
                        "endCoordinates": {
                            "width": item.position.endCoordinates.width,
                            "depth": item.position.endCoordinates.depth,
                            "height": item.position.endCoordinates.height
                        }
                    }
                elif isinstance(item.position, dict):
                    # It's a dictionary
                    position_data = {
                        "startCoordinates": {
                            "width": item.position.get("startCoordinates", {}).get("width", 0),
                            "depth": item.position.get("startCoordinates", {}).get("depth", 0),
                            "height": item.position.get("startCoordinates", {}).get("height", 0)
                        },
                        "endCoordinates": {
                            "width": item.position.get("endCoordinates", {}).get("width", 0),
                            "depth": item.position.get("endCoordinates", {}).get("depth", 0),
                            "height": item.position.get("endCoordinates", {}).get("height", 0)
                        }
                    }
            except AttributeError:
                # Handle any other type gracefully
                position_data = None
        
        waste_items_response.append({
            "itemId": item.itemId,
            "name": item.name,
            "reason": item.reason,
            "containerId": item.containerId,
            "position": position_data
        })
    
    return {
        "success": True,
        "wasteItems": waste_items_response
    }

@router.post("/undock", response_model=UndockingResponse)
async def undock_with_weight_limit(request: UndockingRequest):
    """
    Undock items within a specified weight limit.
    Lower priority items are removed first.
    """
    # Validate weight limit
    if request.maxWeight <= 0:
        raise HTTPException(status_code=400, detail="Maximum weight must be positive")
    
    # Validate timestamp
    try:
        timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Process undocking with weight limit
    items_removed, total_weight = await undock_items_with_weight_limit(request.maxWeight)
    
    return {
        "success": True,
        "itemsRemoved": items_removed,
        "totalWeight": total_weight
    }

@router.post("/complete-undock", response_model=UndockingResponse)
async def complete_undock():
    """
    Complete undocking by removing all expired items from inventory.
    """
    # Process complete undocking (all expired items)
    items_removed, total_weight = await complete_undocking_expired_items()
    
    return {
        "success": True,
        "itemsRemoved": items_removed,
        "totalWeight": total_weight
    }