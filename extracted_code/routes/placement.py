from fastapi import APIRouter, Depends, HTTPException, status
from models.placement import PlacementRequest, PlacementResponse
from models.container import ContainerCreate
from models.item import ItemCreate
from services.placement import place_all_items, generate_rearrangement_plan
from database import items_collection, containers_collection, placements_collection, logs_collection
from datetime import datetime
import copy

router = APIRouter()

@router.post("/placement", response_model=PlacementResponse)
async def create_placement(request: PlacementRequest):
    # Check if we have valid data
    if not request.items or not request.containers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No items or containers provided"
        )
    
    # First, save or update the containers
    for container in request.containers:
        # Check if container already exists
        existing_container = await containers_collection.find_one({"containerId": container.containerId})
        if existing_container:
            # Update existing container
            await containers_collection.update_one(
                {"containerId": container.containerId},
                {"$set": container.dict()}
            )
        else:
            # Insert new container
            container_data = ContainerCreate(**container.dict())
            await containers_collection.insert_one(container_data.dict())
    
    # Then, save or update the items
    for item in request.items:
        # Check if item already exists
        existing_item = await items_collection.find_one({"itemId": item.itemId})
        if existing_item:
            # Update existing item
            await items_collection.update_one(
                {"itemId": item.itemId},
                {"$set": item.dict()}
            )
        else:
            # Insert new item with default values
            item_data = ItemCreate(**item.dict())
            await items_collection.insert_one({
                **item_data.dict(),
                "currentUses": 0,
                "isWaste": False,
                "wasteReason": None
            })
    
    # Get current placements to determine rearrangements
    current_placements = []
    cursor = placements_collection.find({})
    async for doc in cursor:
        current_placements.append(doc)
    
    # Calculate optimal placements
    placements, unplaceable_items = await place_all_items(request.items, request.containers)
    
    # Add isPlaced field to placements
    for placement in placements:
        placement["isPlaced"] = True
    
    # Generate rearrangement plan if needed
    if current_placements and placements:
        _, rearrangements = await generate_rearrangement_plan(
            current_placements, 
            [item for item in request.items if item.itemId not in [u.itemId for u in unplaceable_items]], 
            request.containers
        )
    else:
        rearrangements = []
    
    # Save the new placements
    if placements:
        # Remove previous placements
        item_ids = [p.itemId for p in placements]
        await placements_collection.delete_many({"itemId": {"$in": item_ids}})
        
        # Insert new placements
        await placements_collection.insert_many([p.dict() for p in placements])
        
        # Log the placement operations
        for item_id in item_ids:
            await logs_collection.insert_one({
                "timestamp": datetime.utcnow(),
                "actionType": "placement",
                "itemId": item_id,
                "details": {
                    "operation": "new_placement"
                }
            })
    
    return PlacementResponse(
        success=True,
        placements=placements,
        rearrangements=rearrangements,
        unplaced_items=[{**item.dict(), "isPlaced": False} for item in unplaceable_items]  # Mark unplaced items
    )