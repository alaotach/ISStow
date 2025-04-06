# from fastapi import APIRouter, HTTPException, UploadFile, File
# # from models.item import ItemsImportResponse
# from models.container import ContainersImportResponse
# from database import items_collection, containers_collection, placements_collection
# import csv
# import io
# from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File
from models.item import ItemsImportResponse
from models.container import ContainersImportResponse
from database import items_collection, containers_collection, placements_collection, logs_collection
import csv
import io
from datetime import datetime
from services.placement import place_all_items, save_placements
from models.placement import ItemPlacement, ContainerPlacement
from fastapi.responses import Response
from pymongo import UpdateOne  # Add this import at the top of the file

router = APIRouter(
    prefix="/api",
    tags=["Import/Export"]
)



@router.post("/import/items", response_model=ItemsImportResponse)
async def import_items(file: UploadFile = File(...)):
    """
    Import items from a CSV file and place them in containers.
    Optimized for handling large datasets.
    """
    try:
        # Read CSV file
        content = await file.read()
        csv_data = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_data))
        
        # Skip header row
        header = next(csv_reader)
        
        items_to_insert = []
        items_to_update = []
        items_imported = 0
        errors = []
        imported_items = []
        
        # Batch process items
        for i, row in enumerate(csv_reader, start=2):
            try:
                if len(row) < 9:
                    errors.append({"row": i, "message": f"Not enough columns. Expected 9, got {len(row)}"})
                    continue
                
                item_id, name, width_str, depth_str, height_str, priority_str, expiry_date, usage_limit_str, preferred_zone = row
                
                # Validate numeric fields
                try:
                    width = float(width_str)
                    depth = float(depth_str)
                    height = float(height_str)
                    priority = int(priority_str)
                    usage_limit = int(usage_limit_str)
                except ValueError:
                    errors.append({"row": i, "message": "Invalid numeric value"})
                    continue
                
                # Validate date format
                try:
                    datetime.strptime(expiry_date, "%Y-%m-%d")
                except ValueError:
                    errors.append({"row": i, "message": "Invalid date format. Expected YYYY-MM-DD"})
                    continue
                
                # Prepare item data
                item_data = {
                    "itemId": item_id,
                    "name": name,
                    "width": width,
                    "depth": depth,
                    "height": height,
                    "priority": priority,
                    "expiryDate": expiry_date,
                    "usageLimit": usage_limit,
                    "currentUses": 0,
                    "preferredZone": preferred_zone,
                    "allowNonPreferredZone": True,
                    "isWaste": False,
                    "createdAt": datetime.now().isoformat()
                }
                
                # Check if item already exists
                existing_item = await items_collection.find_one({"itemId": item_id})
                if existing_item:
                    items_to_update.append({"filter": {"itemId": item_id}, "update": {"$set": item_data}})
                else:
                    items_to_insert.append(item_data)
                
                imported_items.append(item_data)
                items_imported += 1
            except Exception as e:
                errors.append({"row": i, "message": str(e)})
        
        # Perform bulk insert and update operations
        if items_to_insert:
            await items_collection.insert_many(items_to_insert)
        if items_to_update:
            bulk_updates = [
                UpdateOne(update["filter"], update["update"]) for update in items_to_update
            ]
            await items_collection.bulk_write(bulk_updates)
        
        # After importing all items, get available containers
        containers = []
        async for container in containers_collection.find({}):
            containers.append(ContainerPlacement(
                containerId=container["containerId"],
                zone=container["zone"],
                width=container["width"],
                depth=container["depth"],
                height=container["height"]
            ))
        
        # Place imported items
        if imported_items and containers:
            placements, unplaced_items = await place_all_items(imported_items, containers)
            
            # Save successful placements
            if placements:
                await save_placements(placements)
            
            # Add unplaced items to errors
            for item in unplaced_items:
                errors.append({
                    "row": "unplaced",
                    "message": f"Could not place item {item['itemId']} in any container"
                })
        
        return ItemsImportResponse(
            success=True,
            itemsImported=items_imported,
            errors=errors
        )
    except Exception as e:
        import traceback
        error_detail = f"Error importing items: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

@router.post("/import/containers", response_model=ContainersImportResponse)
async def import_containers(file: UploadFile = File(...)):
    """
    Import containers from a CSV file
    
    CSV format:
    ContainerID,Zone,Width,Depth,Height
    
    Returns: Number of containers imported and any errors
    """
    try:
        # Read CSV file
        content = await file.read()
        csv_data = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_data))
        
        # Skip header row
        header = next(csv_reader)
        
        containers_imported = 0
        errors = []
        
        for i, row in enumerate(csv_reader, start=2):  # Start from 2 to account for header row
            try:
                if len(row) < 5:
                    errors.append({"row": i, "message": f"Not enough columns. Expected 5, got {len(row)}"})
                    continue
                
                container_id, zone, width_str, depth_str, height_str = row
                
                # Validate numeric fields
                try:
                    width = float(width_str)
                    depth = float(depth_str)
                    height = float(height_str)
                except ValueError:
                    errors.append({"row": i, "message": "Invalid numeric value"})
                    continue
                
                # Check if container already exists
                existing_container = await containers_collection.find_one({"containerId": container_id})
                if existing_container:
                    # Update existing container
                    await containers_collection.update_one(
                        {"containerId": container_id},
                        {"$set": {
                            "zone": zone,
                            "width": width,
                            "depth": depth,
                            "height": height,
                            "updatedAt": datetime.now().isoformat()
                        }}
                    )
                else:
                    # Insert new container
                    await containers_collection.insert_one({
                        "containerId": container_id,
                        "zone": zone,
                        "width": width,
                        "depth": depth,
                        "height": height,
                        "createdAt": datetime.now().isoformat()
                    })
                
                containers_imported += 1
            except Exception as e:
                errors.append({"row": i, "message": str(e)})
        
        return ContainersImportResponse(
            success=True,
            containersImported=containers_imported,
            errors=errors
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error importing containers: {str(e)}")

@router.get("/export/arrangement")
async def export_arrangement():
    """
    Export the current arrangement as a CSV file
    
    Returns: CSV file with current arrangements
    """
    try:
        # Get all placements
        placement_cursor = placements_collection.find()
        placements = await placement_cursor.to_list(length=None)
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Item ID", "Container ID", "Coordinates (W1,D1,H1),(W2,D2,H2)"])
        
        # Write placements
        for placement in placements:
            item_id = placement["itemId"]
            container_id = placement["containerId"]
            position = placement["position"]
            
            start_coords = position["startCoordinates"]
            end_coords = position["endCoordinates"]
            
            coords_str = f"({start_coords['width']},{start_coords['depth']},{start_coords['height']}),({end_coords['width']},{end_coords['depth']},{end_coords['height']})"
            
            writer.writerow([item_id, container_id, coords_str])
        
        # Set file content
        output_str = output.getvalue()
        
        # Return CSV file
        from fastapi.responses import Response
        return Response(
            content=output_str,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=arrangement.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting arrangement: {str(e)}")