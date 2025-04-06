from datetime import datetime
from models.waste import WasteItem
from database import items_collection, containers_collection, placements_collection, waste_collection, logs_collection
from typing import List, Optional, Dict, Any, Tuple

async def identify_waste_items():
    """Identify items that are considered waste (expired or used up)"""
    waste_items = []
    current_date = datetime.utcnow()
    
    # Check all items
    cursor = items_collection.find({})
    async for item in cursor:
        is_waste = False
        reason = None
        
        # Check if already marked as waste
        if item.get("isWaste"):
            is_waste = True
            reason = item.get("wasteReason", "Unknown")
        
        # Check if expired
        if not is_waste and "expiryDate" in item and item["expiryDate"]:
            try:
                # Handle multiple possible date formats
                expiry_date_str = item["expiryDate"]
                if isinstance(expiry_date_str, str):
                    # Try ISO format first
                    try:
                        expiry_date = datetime.fromisoformat(expiry_date_str.replace("Z", "+00:00"))
                    except ValueError:
                        # Try other formats if ISO fails
                        try:
                            # Try RFC 3339 format
                            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            # Try simple date format
                            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
                
                    # Debug log
                    print(f"Comparing dates: expiry_date={expiry_date}, current_date={current_date}")
                    
                    # Check if expired
                    if expiry_date <= current_date:
                        is_waste = True
                        reason = "Expired"
                        
                        # Mark as waste in database
                        await items_collection.update_one(
                            {"itemId": item["itemId"]},
                            {"$set": {"isWaste": True, "wasteReason": "Expired"}}
                        )
                        print(f"Item {item['itemId']} marked as waste (Expired)")
            except Exception as e:
                print(f"Error parsing expiry date for item {item.get('itemId')}: {str(e)}")
                # Don't mark as waste if date parsing fails
                pass
        
        # Check if used up
        if not is_waste and item.get("usageLimit", 0) > 0:
            if item.get("currentUses", 0) >= item.get("usageLimit", 0):
                is_waste = True
                reason = "Out of Uses"
                
                # Mark as waste in database if not already
                if not item.get("isWaste"):
                    await items_collection.update_one(
                        {"itemId": item["itemId"]},
                        {"$set": {"isWaste": True, "wasteReason": "Out of Uses"}}
                    )
                    print(f"Item {item['itemId']} marked as waste (Out of Uses)")
        
        # If waste, add to the list
        if is_waste:
            # Get placement info
            placement = await placements_collection.find_one({"itemId": item["itemId"]})
            container_id = None
            position = None
            module = None
            location_position = None
            
            if placement:
                container_id = placement.get("containerId")
                position = placement.get("position")
                
                # Try to get container info for location
                if container_id:
                    container = await containers_collection.find_one({"containerId": container_id})
                    if container:
                        module = container.get("zone")
            
            # Create location object only if we have data
            location = None
            if module or location_position:
                location = {
                    "module": module or "Unknown",
                    "position": location_position or "Unknown"
                }
            
            # Calculate weight or use default
            weight = await calculate_item_weight(item["itemId"])
            
            # Get disposal date if available
            disposal_date = item.get("disposalDate")
            
            waste_items.append(WasteItem(
                itemId=item["itemId"],
                name=item.get("name", "Unknown Item"),
                reason=reason,
                containerId=container_id,
                position=position if position else None,
                location=location,
                weight=weight,
                disposalDate=disposal_date
            ))
    
    return waste_items

async def calculate_item_weight(item_id: str) -> float:
    """Calculate weight of an item based on dimensions"""
    item = await items_collection.find_one({"itemId": item_id})
    if not item:
        return 0
    
    # If weight is directly available
    if "weight" in item and item["weight"]:
        return float(item["weight"])
    
    # Calculate from dimensions if available
    if all(dim in item and item[dim] for dim in ["width", "depth", "height"]):
        volume = item.get("width", 0) * item.get("depth", 0) * item.get("height", 0)
        # Assuming a density factor
        density_factor = 0.0001  # kg per cubic cm
        return volume * density_factor
    
    # Default weight if nothing else is available
    return 0.5  # Default to 0.5kg

async def undock_items_with_weight_limit(max_weight: float) -> Tuple[int, float]:
    """
    Undock items within a weight limit, prioritizing lower priority items.
    
    Returns:
        Tuple containing:
        - Number of items removed
        - Total weight of removed items
    """
    # Identify waste items
    waste_items = await identify_waste_items()
    
    # Calculate weights and sort items by priority (lowest first)
    items_with_weight = []
    for waste_item in waste_items:
        # Get item details to check priority
        item = await items_collection.find_one({"itemId": waste_item.itemId})
        if not item:
            continue
            
        weight = await calculate_item_weight(waste_item.itemId)
        priority = item.get("priority", 50)  # Default priority if not specified
        
        items_with_weight.append({
            "item": waste_item,
            "weight": weight,
            "priority": priority
        })
    
    # Sort by priority (lowest first)
    items_with_weight.sort(key=lambda x: x["priority"])
    
    # Remove items within weight limit
    removed_items = []
    total_weight = 0
    
    for item_data in items_with_weight:
        if total_weight + item_data["weight"] <= max_weight:
            # Add item to removal list
            removed_items.append(item_data["item"].itemId)
            total_weight += item_data["weight"]
    
    # Process item removal
    if removed_items:
        # Remove from placements
        await placements_collection.delete_many({"itemId": {"$in": removed_items}})
        
        # Remove from items collection
        await items_collection.delete_many({"itemId": {"$in": removed_items}})
        
        # Log the undocking
        for item_id in removed_items:
            await logs_collection.insert_one({
                "timestamp": datetime.utcnow(),
                "actionType": "disposal",
                "itemId": item_id,
                "details": {
                    "reason": "undocked",
                    "weight": await calculate_item_weight(item_id)
                }
            })
    
    return len(removed_items), total_weight

async def complete_undocking_expired_items() -> Tuple[int, float]:
    """
    Remove all expired items from inventory during complete undocking.
    
    Returns:
        Tuple containing:
        - Number of items removed
        - Total weight of removed items
    """
    # Find all expired items (those marked as waste with reason "Expired")
    expired_items = []
    cursor = items_collection.find({"isWaste": True, "wasteReason": "Expired"})
    
    async for item in cursor:
        expired_items.append(item["itemId"])
    
    # Calculate total weight
    total_weight = 0
    for item_id in expired_items:
        total_weight += await calculate_item_weight(item_id)
    
    # Process item removal
    if expired_items:
        # Remove from placements
        await placements_collection.delete_many({"itemId": {"$in": expired_items}})
        
        # Remove from items collection
        await items_collection.delete_many({"itemId": {"$in": expired_items}})
        
        # Log the undocking
        for item_id in expired_items:
            await logs_collection.insert_one({
                "timestamp": datetime.utcnow(),
                "actionType": "disposal",
                "itemId": item_id,
                "details": {
                    "reason": "expired",
                    "weight": await calculate_item_weight(item_id)
                }
            })
    
    return len(expired_items), total_weight