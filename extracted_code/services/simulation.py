from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from models.simulation import SimulationRequest, SimulationResponse, SimulationChanges
from database import items_collection, simulation_collection, logs_collection
import copy

async def get_current_simulation_date():
    """Get the current simulation date from the database or use current time"""
    sim_state = await simulation_collection.find_one({"type": "current_state"})
    
    if not sim_state:
        # Initialize simulation state if not exists
        current_date = datetime.utcnow()
        sim_state = {
            "type": "current_state",
            "currentDate": current_date,
            "createdAt": current_date,
            "updatedAt": current_date
        }
        await simulation_collection.insert_one(sim_state)
        return current_date
    else:
        # Handle both string and datetime types
        if isinstance(sim_state["currentDate"], str):
            try:
                return datetime.fromisoformat(sim_state["currentDate"].replace("Z", "+00:00"))
            except ValueError:
                # If parsing fails, return current time
                print(f"Failed to parse date {sim_state['currentDate']}, using current time instead")
                return datetime.utcnow()
        else:
            # It's already a datetime object
            return sim_state["currentDate"]

async def update_simulation_date(new_date: datetime):
    """Update the current simulation date in the database"""
    await simulation_collection.update_one(
        {"type": "current_state"},
        {"$set": {
            "currentDate": new_date.isoformat(),
            "updatedAt": datetime.utcnow()
        }},
        upsert=True
    )

async def advance_simulation_time(days: Optional[int] = None, 
                                 to_timestamp: Optional[str] = None,
                                 items_to_use: Optional[List[Dict[str, str]]] = None) -> SimulationResponse:
    """
    Advance simulation time by a number of days or to a specific date.
    
    Args:
        days: Number of days to advance
        to_timestamp: Specific date to advance to (ISO format)
        items_to_use: List of items to be used each day
        
    Returns:
        SimulationResponse with changes that occurred
    """
    # Get current simulation date
    current_date = await get_current_simulation_date()
    
    # Determine target date
    if days is not None and days > 0:
        target_date = current_date + timedelta(days=days)
    elif to_timestamp:
        try:
            target_date = datetime.fromisoformat(to_timestamp.replace("Z", "+00:00"))
            if target_date <= current_date:
                raise ValueError("Target date must be in the future")
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {str(e)}")
    else:
        # Default to one day if neither is provided
        target_date = current_date + timedelta(days=1)
    
    # Calculate days difference for iteration
    days_diff = (target_date - current_date).days
    if days_diff <= 0:
        days_diff = 1  # Ensure at least one day passes
    
    # Prepare changes tracking
    changes = {
        "itemsUsed": [],
        "itemsExpired": [],
        "itemsDepletedToday": []
    }
    
    # Create a list of item IDs to use daily (handle None case)
    items_to_use_ids = []
    if items_to_use:
        for item_usage in items_to_use:
            if item_usage.get("itemId"):
                items_to_use_ids.append(item_usage["itemId"])
            elif item_usage.get("name"):
                # Find item by name (case-insensitive)
                item = await items_collection.find_one(
                    {"name": {"$regex": f"^{item_usage['name']}$", "$options": "i"}}
                )
                if item:
                    items_to_use_ids.append(item["itemId"])
    
    # Simulate the passage of time day by day
    for day in range(days_diff):
        # Current day's date
        day_date = current_date + timedelta(days=day + 1)
        
        # 1. Process item usage
        for item_id in items_to_use_ids:
            # Get the item
            item = await items_collection.find_one({"itemId": item_id})
            if not item or item.get("isWaste"):
                continue  # Skip if item doesn't exist or is already waste
            
            # Update usage count
            current_uses = item.get("currentUses", 0) + 1
            usage_limit = item.get("usageLimit")
            
            # Check if item is now depleted
            is_depleted = False
            if usage_limit and current_uses >= usage_limit:
                # Mark as waste
                await items_collection.update_one(
                    {"itemId": item_id},
                    {"$set": {
                        "isWaste": True, 
                        "wasteReason": "Out of Uses", 
                        "currentUses": current_uses
                    }}
                )
                is_depleted = True
                
                # Add to depleted items list
                changes["itemsDepletedToday"].append({
                    "itemId": item_id,
                    "name": item["name"]
                })
            else:
                # Just update usage count
                await items_collection.update_one(
                    {"itemId": item_id},
                    {"$set": {"currentUses": current_uses}}
                )
            
            # Add to used items list
            changes["itemsUsed"].append({
                "itemId": item_id,
                "name": item["name"],
                "remainingUses": (usage_limit - current_uses) if usage_limit else None
            })
            
            # Log usage
            await logs_collection.insert_one({
                "timestamp": day_date.isoformat(),
                "actionType": "item_usage",
                "itemId": item_id,
                "details": {
                    "currentUses": current_uses,
                    "isWaste": is_depleted,
                    "remainingUses": (usage_limit - current_uses) if usage_limit else None
                }
            })
    
    # 2. Check for expired items at the target date
    cursor = items_collection.find({"expiryDate": {"$ne": None}, "isWaste": {"$ne": True}})
    async for item in cursor:
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
                print(f"Simulation checking dates: expiry_date={expiry_date}, target_date={target_date}")
                
                # Check if the item is expired at the target date
                if expiry_date <= target_date:
                    # Mark as waste
                    await items_collection.update_one(
                        {"itemId": item["itemId"]},
                        {"$set": {"isWaste": True, "wasteReason": "Expired"}}
                    )
                    
                    # Add to expired items list
                    changes["itemsExpired"].append({
                        "itemId": item["itemId"],
                        "name": item["name"]
                    })
                    
                    # Log expiration
                    await logs_collection.insert_one({
                        "timestamp": target_date.isoformat(),
                        "actionType": "item_expiration",
                        "itemId": item["itemId"],
                        "details": {
                            "expiryDate": item["expiryDate"],
                            "simulationDate": target_date.isoformat()
                        }
                    })
                    
                    print(f"Item {item['itemId']} marked as expired in simulation")
        except Exception as e:
            # Log the error but continue processing other items
            print(f"Error checking expiry for item {item.get('itemId')}: {str(e)}")
            continue
    
    # Update simulation current date
    await update_simulation_date(target_date)
    
    # Create log entry for this simulation, handling empty items case
    await simulation_collection.insert_one({
        "type": "simulation_log",
        "fromDate": current_date.isoformat(),
        "toDate": target_date.isoformat(),
        "daysPassed": days_diff,
        "itemsUsed": [item_id for item_id in items_to_use_ids] if items_to_use_ids else [],
        "changes": changes,
        "createdAt": datetime.utcnow()
    })
    
    # Return simulation results
    return SimulationResponse(
        success=True,
        newDate=target_date.isoformat(),
        changes=SimulationChanges(
            itemsUsed=changes["itemsUsed"],
            itemsExpired=changes["itemsExpired"],
            itemsDepletedToday=changes["itemsDepletedToday"]
        )
    )

async def reset_simulation():
    """Reset the simulation date to the current date"""
    current_date = datetime.utcnow()
    await update_simulation_date(current_date)
    
    # Log reset
    await simulation_collection.insert_one({
        "type": "simulation_reset",
        "resetDate": current_date.isoformat(),
        "createdAt": current_date
    })
    
    return {
        "success": True,
        "resetDate": current_date.isoformat()
    }

async def get_simulation_history(limit: int = 10):
    """Get history of simulation runs"""
    logs = []
    cursor = simulation_collection.find(
        {"type": {"$in": ["simulation_log", "simulation_reset"]}}
    ).sort("createdAt", -1).limit(limit)
    
    async for log in cursor:
        # Sanitize the MongoDB _id field
        log["_id"] = str(log["_id"])
        logs.append(log)
    
    return logs