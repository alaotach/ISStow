from models.item import Position, Coordinates
from database import items_collection, containers_collection, placements_collection, logs_collection
from datetime import datetime
from typing import List, Dict, Any, Optional

def get_position_depth(position_obj):
    """Helper function to safely get the depth value from a position object"""
    if isinstance(position_obj, dict):
        # Dictionary access
        start_coords = position_obj.get("startCoordinates", {})
        if isinstance(start_coords, dict):
            return start_coords.get("depth", 0)
        else:
            # Pydantic model
            return getattr(start_coords, "depth", 0)
    else:
        # Pydantic model
        start_coords = getattr(position_obj, "startCoordinates", None)
        if start_coords:
            return getattr(start_coords, "depth", 0)
        return 0


async def find_item_by_id(item_id: str):
    """Find an item by its ID"""
    # Get the item details
    item = await items_collection.find_one({"itemId": item_id})
    if not item:
        return None
    
    # Get the placement information
    placement = await placements_collection.find_one({"itemId": item_id})
    if not placement:
        return {"item": item, "placement": None}
    
    # Get container information
    container = await containers_collection.find_one({"containerId": placement["containerId"]})
    
    return {"item": item, "placement": placement, "container": container}

async def find_item_by_name(item_name: str):
    """Find items by name (partial match)"""
    # Search for items matching the name
    cursor = items_collection.find({"name": {"$regex": item_name, "$options": "i"}})
    items = []
    async for item in cursor:
        items.append(item)
    
    if not items:
        return []
    
    # Get placement and container info for each item
    result = []
    for item in items:
        placement = await placements_collection.find_one({"itemId": item["itemId"]})
        if placement:
            container = await containers_collection.find_one({"containerId": placement["containerId"]})
            result.append({"item": item, "placement": placement, "container": container})
        else:
            result.append({"item": item, "placement": None, "container": None})
    
    return result

async def identify_items_to_move(item_id: str, position: Position, container_id: str):
    """
    Identify which items need to be moved to access the target item
    Returns items in the order they should be moved
    """
    # Get all items in the same container
    cursor = placements_collection.find({"containerId": container_id})
    items_in_container = []
    async for doc in cursor:
        items_in_container.append(doc)
    
    # Get actual item details for each placement
    for i, placement in enumerate(items_in_container):
        item = await items_collection.find_one({"itemId": placement["itemId"]})
        if item:
            items_in_container[i]["name"] = item["name"]
    
    # Target item's position
    target_start = position.startCoordinates
    target_end = position.endCoordinates
    
    # Items that need to be moved are those that are in front of or stacked on top of the target
    items_to_move = []
    
    for placement in items_in_container:
        if placement["itemId"] == item_id:
            continue  # Skip the target item itself
        
        # Safely handle different position data formats
        item_position = placement["position"]
        
        # Handle if position is dictionary or Pydantic model
        if isinstance(item_position, dict):
            item_start_coords = item_position.get("startCoordinates", {})
            item_end_coords = item_position.get("endCoordinates", {})
            
            # Handle if coordinates are dictionaries or Pydantic models
            if isinstance(item_start_coords, dict):
                item_start_width = item_start_coords.get("width", 0)
                item_start_depth = item_start_coords.get("depth", 0)
                item_start_height = item_start_coords.get("height", 0)
            else:
                item_start_width = getattr(item_start_coords, "width", 0)
                item_start_depth = getattr(item_start_coords, "depth", 0)
                item_start_height = getattr(item_start_coords, "height", 0)
                
            if isinstance(item_end_coords, dict):
                item_end_width = item_end_coords.get("width", 0)
                item_end_depth = item_end_coords.get("depth", 0)
                item_end_height = item_end_coords.get("height", 0)
            else:
                item_end_width = getattr(item_end_coords, "width", 0)
                item_end_depth = getattr(item_end_coords, "depth", 0)
                item_end_height = getattr(item_end_coords, "height", 0)
        else:
            # Position is a Pydantic model
            item_start_coords = getattr(item_position, "startCoordinates", None)
            item_end_coords = getattr(item_position, "endCoordinates", None)
            
            item_start_width = getattr(item_start_coords, "width", 0) if item_start_coords else 0
            item_start_depth = getattr(item_start_coords, "depth", 0) if item_start_coords else 0
            item_start_height = getattr(item_start_coords, "height", 0) if item_start_coords else 0
            
            item_end_width = getattr(item_end_coords, "width", 0) if item_end_coords else 0
            item_end_depth = getattr(item_end_coords, "depth", 0) if item_end_coords else 0
            item_end_height = getattr(item_end_coords, "height", 0) if item_end_coords else 0
        
        # Handle target coordinates in the same way
        if isinstance(target_start, dict):
            target_start_width = target_start.get("width", 0)
            target_start_depth = target_start.get("depth", 0)
            target_start_height = target_start.get("height", 0)
        else:
            target_start_width = getattr(target_start, "width", 0)
            target_start_depth = getattr(target_start, "depth", 0)
            target_start_height = getattr(target_start, "height", 0)
            
        if isinstance(target_end, dict):
            target_end_width = target_end.get("width", 0)
            target_end_depth = target_end.get("depth", 0)
            target_end_height = target_end.get("height", 0)
        else:
            target_end_width = getattr(target_end, "width", 0)
            target_end_depth = getattr(target_end, "depth", 0)
            target_end_height = getattr(target_end, "height", 0)
        
        # Check x-coordinate overlap
        x_overlap = (
            (item_start_width <= target_end_width and item_end_width >= target_start_width) or
            (target_start_width <= item_end_width and target_end_width >= item_start_width)
        )
        
        # Check if item is in front of target
        in_front = item_end_depth <= target_start_depth
        
        if x_overlap and in_front:
            items_to_move.append({
                "itemId": placement["itemId"],
                "name": placement.get("name", "Unknown Item"),
                "position": placement["position"],
                "distance": target_start_depth - item_end_depth  # How far in front
            })
    
    # Sort items by position - we want to move items from front to back
    # Fixed sorting function that doesn't use the incorrect getattr call
    items_to_move.sort(key=lambda x: get_position_depth(x["position"]))
    
    return items_to_move

async def generate_retrieval_steps(item_data, items_to_move):
    """Generate step-by-step instructions for retrieving an item"""
    steps = []
    step_counter = 1
    
    # If no items need to be moved, simple retrieval
    if not items_to_move:
        steps.append({
            "step": step_counter,
            "action": "retrieve",
            "itemId": item_data["item"]["itemId"],
            "itemName": item_data["item"]["name"]
        })
        return steps
    
    # Generate steps for moving other items aside first
    for item_to_move in items_to_move:
        steps.append({
            "step": step_counter,
            "action": "remove",
            "itemId": item_to_move["itemId"],
            "itemName": item_to_move["name"]
        })
        step_counter += 1
        
        steps.append({
            "step": step_counter,
            "action": "setAside",
            "itemId": item_to_move["itemId"],
            "itemName": item_to_move["name"]
        })
        step_counter += 1
    
    # Retrieve the target item
    steps.append({
        "step": step_counter,
        "action": "retrieve",
        "itemId": item_data["item"]["itemId"],
        "itemName": item_data["item"]["name"]
    })
    step_counter += 1
    
    # Place moved items back (in reverse order)
    for item_to_move in reversed(items_to_move):
        steps.append({
            "step": step_counter,
            "action": "placeBack",
            "itemId": item_to_move["itemId"],
            "itemName": item_to_move["name"]
        })
        step_counter += 1
    
    return steps

async def mark_item_as_used(item_id: str, user_id: Optional[str] = None):
    """Mark an item as used (increment usage counter)"""
    # Get the current item
    item = await items_collection.find_one({"itemId": item_id})
    if not item:
        return False
    
    # Increment the current uses
    current_uses = item.get("currentUses", 0) + 1
    usage_limit = item.get("usageLimit", 0)
    
    # Update the item
    await items_collection.update_one(
        {"itemId": item_id},
        {"$set": {"currentUses": current_uses}}
    )
    
    # If item has reached usage limit, mark as waste
    if usage_limit > 0 and current_uses >= usage_limit:
        await items_collection.update_one(
            {"itemId": item_id},
            {"$set": {"isWaste": True, "wasteReason": "Out of Uses"}}
        )
    
    # Log the retrieval
    await logs_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "userId": user_id,
        "actionType": "retrieval",
        "itemId": item_id,
        "details": {
            "operation": "used",
            "currentUses": current_uses
        }
    })
    
    return True

async def place_item(item_id: str, container_id: str, position: Position, user_id: Optional[str] = None):
    """Place an item in a specific container and position"""
    # Check if item exists
    item = await items_collection.find_one({"itemId": item_id})
    if not item:
        return False
    
    # Check if container exists
    container = await containers_collection.find_one({"containerId": container_id})
    if not container:
        return False
    
    # Update or create placement
    placement = await placements_collection.find_one({"itemId": item_id})
    if placement:
        await placements_collection.update_one(
            {"itemId": item_id},
            {"$set": {
                "containerId": container_id,
                "position": position.dict()
            }}
        )
    else:
        await placements_collection.insert_one({
            "itemId": item_id,
            "containerId": container_id,
            "position": position.dict()
        })
    
    # Log the placement
    await logs_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "userId": user_id,
        "actionType": "placement",
        "itemId": item_id,
        "details": {
            "containerId": container_id,
            "position": position.dict()
        }
    })
    
    return True