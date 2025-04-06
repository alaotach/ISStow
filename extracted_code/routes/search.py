from fastapi import APIRouter, Depends, HTTPException, status, Query
from models.item import Position
from services.search import find_item_by_id, find_item_by_name, identify_items_to_move, generate_retrieval_steps, mark_item_as_used, place_item
from database import logs_collection
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

class ItemDetails(BaseModel):
    itemId: str
    name: str
    containerId: str
    zone: str
    position: Position
    isPlaced: bool  # Add isPlaced field

class RetrievalStep(BaseModel):
    step: int
    action: str
    itemId: str
    itemName: str

class SearchResponse(BaseModel):
    success: bool
    found: bool
    item: Optional[ItemDetails] = None
    retrievalSteps: list[RetrievalStep] = []

class RetrieveRequest(BaseModel):
    itemId: str
    userId: Optional[str] = None
    timestamp: str

class PlaceRequest(BaseModel):
    itemId: str
    userId: Optional[str] = None
    timestamp: str
    containerId: str
    position: Position

class SimpleResponse(BaseModel):
    success: bool
    message: Optional[str] = None

@router.get("/search", response_model=SearchResponse)
async def search_item(
    id: Optional[str] = Query(None, alias="id"),
    name: Optional[str] = Query(None, alias="name"),
    userId: Optional[str] = None
):
    """
    Search for an item by ID or name
    """
    # Check if at least one search parameter is provided
    if not id and not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either id or name parameter must be provided"
        )
    
    try:
        # Search by ID first if provided
        if id:
            item_data = await find_item_by_id(id)
        # Fall back to name search if no ID provided or no item found by ID
        elif name:
            items_data = await find_item_by_name(name)
            item_data = items_data[0] if items_data else None
        else:
            return SearchResponse(success=True, found=False)

        if not item_data:
            return SearchResponse(success=True, found=False)

        # Log the search if userId provided
        if userId:
            await logs_collection.insert_one({
                "timestamp": datetime.utcnow(),
                "userId": userId,
                "actionType": "search",
                "itemId": id or "name_search",
                "details": {"searchType": "id" if id else "name"}
            })

        # If item is not placed, return basic item details
        if not item_data.get("placement"):
            return SearchResponse(
                success=True,
                found=True,
                item=ItemDetails(
                    itemId=item_data["item"]["itemId"],
                    name=item_data["item"]["name"],
                    containerId=None,
                    zone=None,
                    position=None,
                    isPlaced=False
                ),
                retrievalSteps=[]
            )

        # Generate retrieval steps if item is placed
        items_to_move = await identify_items_to_move(
            item_data["item"]["itemId"],
            Position(**item_data["placement"]["position"]),
            item_data["placement"]["containerId"]
        )
        
        retrieval_steps = await generate_retrieval_steps(item_data, items_to_move)

        return SearchResponse(
            success=True,
            found=True,
            item=ItemDetails(
                itemId=item_data["item"]["itemId"],
                name=item_data["item"]["name"],
                containerId=item_data["placement"]["containerId"],
                zone=item_data["container"]["zone"],
                position=Position(**item_data["placement"]["position"]),
                isPlaced=True
            ),
            retrievalSteps=retrieval_steps
        )

    except Exception as e:
        print(f"Search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during search: {str(e)}"
        )

@router.post("/retrieve", response_model=SimpleResponse)
async def retrieve_item(request: RetrieveRequest):
    # Check if item exists
    item_data = await find_item_by_id(request.itemId)
    if not item_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {request.itemId} not found"
        )
    
    # Mark the item as used
    result = await mark_item_as_used(request.itemId, request.userId)
    
    return SimpleResponse(
        success=result,
        message="Item retrieved and marked as used successfully" if result else "Failed to mark item as used"
    )

@router.post("/place", response_model=SimpleResponse)
async def place_item_endpoint(request: PlaceRequest):
    # Place the item in the specified container
    result = await place_item(
        request.itemId,
        request.containerId,
        request.position,
        request.userId
    )
    
    return SimpleResponse(
        success=result,
        message="Item placed successfully" if result else "Failed to place item"
    )