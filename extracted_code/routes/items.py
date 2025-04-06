from fastapi import APIRouter, HTTPException
from typing import List
from models.item import ItemResponse
from database import items_collection, placements_collection, containers_collection

router = APIRouter(
    prefix="/api",
    tags=["Items"]
)

@router.get("/items", response_model=List[ItemResponse])
async def get_items():
    """
    Retrieve all items with their current placement status
    """
    try:
        items = []
        cursor = items_collection.find({})
        
        async for item in cursor:
            # Get placement information for this item
            placement_data = await placements_collection.find_one({
                "itemId": item["itemId"]
            })
            
            if placement_data:
                # Get container information
                container = await containers_collection.find_one({
                    "containerId": placement_data["containerId"]
                })
                
                item.update({
                    "isPlaced": True,
                    "containerId": placement_data["containerId"],
                    "actualZone": container["zone"] if container else None,
                    "containerName": container.get("name", container["containerId"]) if container else None,
                    "position": {
                        "startCoordinates": placement_data["position"]["startCoordinates"],
                        "endCoordinates": placement_data["position"]["endCoordinates"]
                    } if "position" in placement_data else None
                })
            else:
                item.update({
                    "isPlaced": False,
                    "containerId": None,
                    "actualZone": None,
                    "containerName": None,
                    "position": None
                })
            
            print(f"Debug - Item {item['itemId']}: isPlaced={item['isPlaced']}, position={item.get('position')}")
            items.append(item)
        
        return items
        
    except Exception as e:
        print(f"Error fetching items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: str):
    """
    Retrieve a specific item by ID
    """
    item = await items_collection.find_one({"itemId": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Convert ObjectId to string
    if "_id" in item:
        item["_id"] = str(item["_id"])
    
    # Set default values for optional fields
    item["isPlaced"] = item.get("isPlaced", False)
    item["actualZone"] = item.get("actualZone")
    item["wasteReason"] = item.get("wasteReason")
    
    return item
