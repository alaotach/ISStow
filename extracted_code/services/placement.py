from models.placement import PlacementBase, RearrangementStep, Position
from models.item import Coordinates
from database import items_collection, containers_collection, placements_collection
from datetime import datetime
import copy

# Add this helper function to the top of the file
def get_attr(obj, attr):
    """Safely get attribute from either a dict or an object"""
    if hasattr(obj, attr):
        return getattr(obj, attr)
    elif isinstance(obj, dict) and attr in obj:
        return obj[attr]
    return None

async def check_item_fits_container(container, dimensions):
    """Check if an item can physically fit in a container regardless of current position"""
    return all(dimensions[i] <= container[i] for i in range(3))

async def is_space_free(occupied_spaces, pos, dimensions):
    """Check if a space is free (has no overlaps with existing items)"""
    for x in range(int(pos[0]), int(pos[0] + dimensions[0])):
        for y in range(int(pos[1]), int(pos[1] + dimensions[1])):
            for z in range(int(pos[2]), int(pos[2] + dimensions[2])):
                if (x, y, z) in occupied_spaces:
                    return False
    return True

async def mark_space_occupied(occupied_spaces, pos, dimensions):
    """Mark a space as occupied by an item"""
    for x in range(int(pos[0]), int(pos[0] + dimensions[0])):
        for y in range(int(pos[1]), int(pos[1] + dimensions[1])):
            for z in range(int(pos[2]), int(pos[2] + dimensions[2])):
                occupied_spaces.add((x, y, z))

async def get_corners(pos, dimensions):
    x, y, z = pos
    w, d, h = dimensions
    return [
        [x, y, z],           # bottom-left-front
        [x+w, y, z],         # bottom-right-front
        [x, y+d, z],         # bottom-left-back
        [x+w, y+d, z],       # bottom-right-back
        [x, y, z+h],         # top-left-front
        [x+w, y, z+h],       # top-right-front
        [x, y+d, z+h],       # top-left-back
        [x+w, y+d, z+h]      # top-right-back
    ]

async def place_items_with_priority(container, items_to_place):
    """
    Optimized placement logic for handling large datasets.
    """
    # Sort items by priority (highest first)
    items_list = sorted(
        items_to_place,
        key=lambda x: x.get("priority", 0) if isinstance(x, dict) else x.priority,
        reverse=True
    )
    placed_items = []
    unplaceable_items = []
    
    # Track occupied spaces
    occupied_spaces = set()
    max_depth_at_x = {}
    
    for item in items_list:
        dimensions = (
            [item.get("width"), item.get("depth"), item.get("height")]
            if isinstance(item, dict)
            else [item.width, item.depth, item.height]
        )
        container_dims = [container.width, container.depth, container.height]
        
        if not await check_item_fits_container(container_dims, dimensions):
            unplaceable_items.append(item)
            continue
        
        # Try to find a suitable position
        item_placed = False
        for x_start in range(0, int(container.width - dimensions[0]) + 1):
            current_depth = max(max_depth_at_x.get(x, 0) for x in range(x_start, x_start + int(dimensions[0])))
            pos = [x_start, current_depth, 0]
            
            if pos[1] + dimensions[1] <= container.depth and await is_space_free(occupied_spaces, pos, dimensions):
                await mark_space_occupied(occupied_spaces, pos, dimensions)
                for x in range(x_start, x_start + int(dimensions[0])):
                    max_depth_at_x[x] = max(max_depth_at_x.get(x, 0), pos[1] + dimensions[1])
                
                placed_items.append(PlacementBase(
                    itemId=item.get("itemId") if isinstance(item, dict) else item.itemId,
                    containerId=container.containerId,
                    position=Position(
                        startCoordinates=Coordinates(width=pos[0], depth=pos[1], height=pos[2]),
                        endCoordinates=Coordinates(width=pos[0] + dimensions[0], depth=pos[1] + dimensions[1], height=pos[2] + dimensions[2])
                    )
                ))
                item_placed = True
                break
        
        if not item_placed:
            unplaceable_items.append(item)
    
    return placed_items, unplaceable_items

# Fix for the generate_rearrangement_plan function

async def generate_rearrangement_plan(current_placements, items_to_rearrange, containers):
    """Generate a plan for rearranging items to optimize placement"""
    rearrangements = []
    step_counter = 1
    
    # Helper function to safely get attributes from either dict or object
    def get_attr(obj, attr):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        elif isinstance(obj, dict) and attr in obj:
            return obj[attr]
        return None
    
    # First, gather all current placements for reference
    current_placement_map = {}
    for placement in current_placements:
        item_id = get_attr(placement, 'itemId')
        if item_id:
            current_placement_map[item_id] = placement
    
    # Generate new optimal placements
    new_placements = []
    unplaceable_items = []
    
    # Try to place items in each container
    for container in containers:
        # Get items that prefer this container's zone
        container_zone = get_attr(container, 'zone')
        preferred_items = []
        
        for item in items_to_rearrange:
            item_id = get_attr(item, 'itemId')
            item_zone = get_attr(item, 'preferredZone')
            
            # Check if item is already in a new placement
            already_placed = any(get_attr(p, 'itemId') == item_id for p in new_placements)
            already_unplaceable = any(get_attr(u, 'itemId') == item_id for u in unplaceable_items)
            
            if item_zone == container_zone and not already_placed and not already_unplaceable:
                preferred_items.append(item)
        
        # Place items with priority
        if preferred_items:
            placed, unplaced = await place_items_with_priority(container, preferred_items)
            new_placements.extend(placed)
            unplaceable_items.extend(unplaced)
    
    # Try to place remaining items in any container
    remaining_items = []
    for item in items_to_rearrange:
        item_id = get_attr(item, 'itemId')
        already_placed = any(get_attr(p, 'itemId') == item_id for p in new_placements)
        already_unplaceable = any(get_attr(u, 'itemId') == item_id for u in unplaceable_items)
        
        if not already_placed and not already_unplaceable:
            remaining_items.append(item)
    
    for container in containers:
        if not remaining_items:
            break
            
        placed, unplaced = await place_items_with_priority(container, remaining_items)
        new_placements.extend(placed)
        
        # Update remaining items
        new_remaining = []
        for item in remaining_items:
            item_id = get_attr(item, 'itemId')
            if not any(get_attr(p, 'itemId') == item_id for p in placed):
                new_remaining.append(item)
        remaining_items = new_remaining
    
    # Any items left are unplaceable
    unplaceable_items.extend(remaining_items)
    
    # Generate rearrangement steps by comparing current to new positions
    for item in items_to_rearrange:
        item_id = get_attr(item, 'itemId')
        current_placement = current_placement_map.get(item_id)
        
        # Find matching new placement
        new_placement = None
        for p in new_placements:
            if get_attr(p, 'itemId') == item_id:
                new_placement = p
                break
        
        # Skip if item can't be placed in new arrangement
        if not new_placement:
            continue
            
        # If item was already placed somewhere
        if current_placement:
            current_container = get_attr(current_placement, 'containerId')
            new_container = get_attr(new_placement, 'containerId')
            
            # Get position data
            if hasattr(current_placement, 'position'):
                current_pos = current_placement.position
                current_start = current_pos.startCoordinates
                current_start_width = current_start.width
                current_start_depth = current_start.depth
                current_start_height = current_start.height
            elif isinstance(current_placement, dict) and 'position' in current_placement:
                current_pos = current_placement['position']
                current_start = current_pos.get('startCoordinates', {})
                current_start_width = current_start.get('width', 0)
                current_start_depth = current_start.get('depth', 0)
                current_start_height = current_start.get('height', 0)
            else:
                # Can't determine current position
                current_start_width = None
                current_start_depth = None
                current_start_height = None
            
            if hasattr(new_placement, 'position'):
                new_pos = new_placement.position
                new_start = new_pos.startCoordinates
                new_start_width = new_start.width
                new_start_depth = new_start.depth
                new_start_height = new_start.height
            elif isinstance(new_placement, dict) and 'position' in new_placement:
                new_pos = new_placement['position']
                new_start = new_pos.get('startCoordinates', {})
                new_start_width = new_start.get('width', 0)
                new_start_depth = new_start.get('depth', 0)
                new_start_height = new_start.get('height', 0)
            else:
                # Can't determine new position
                new_start_width = None
                new_start_depth = None
                new_start_height = None
            
            # Check if position changed
            position_changed = (
                current_container != new_container or
                current_start_width != new_start_width or
                current_start_depth != new_start_depth or
                current_start_height != new_start_height
            )
            
            if position_changed:
                # Add removal step
                rearrangements.append(RearrangementStep(
                    step=step_counter,
                    action="remove",
                    itemId=item_id,
                    fromContainer=current_container,
                    fromPosition=get_attr(current_placement, 'position')
                ))
                step_counter += 1
                
                # Add placement step
                rearrangements.append(RearrangementStep(
                    step=step_counter,
                    action="place",
                    itemId=item_id,
                    toContainer=new_container,
                    toPosition=get_attr(new_placement, 'position')
                ))
                step_counter += 1
        else:
            # Item not previously placed, just add a placement step
            rearrangements.append(RearrangementStep(
                step=step_counter,
                action="place",
                itemId=item_id,
                toContainer=get_attr(new_placement, 'containerId'),
                toPosition=get_attr(new_placement, 'position')
            ))
            step_counter += 1
    
    return new_placements, rearrangements

async def place_all_items(items, containers):
    """Place all items in available containers with optimal arrangement"""
    try:
        # Convert items to sorted list by priority (highest first)
        sorted_items = sorted(
            items, 
            key=lambda x: x.get("priority", 0) if isinstance(x, dict) else x.priority, 
            reverse=True
        )
        
        placements = []
        unplaceable_items = []
        attempted_items = set()  # Track items we've already tried to place
        
        # Group containers by zone for better organization
        containers_by_zone = {}
        for container in containers:
            if container.zone not in containers_by_zone:
                containers_by_zone[container.zone] = []
            containers_by_zone[container.zone].append(container)
        
        # First pass: place high-priority items in their preferred zones
        for zone, zone_containers in containers_by_zone.items():
            preferred_high_priority = [
                item for item in sorted_items 
                if item.get("priority", 0) >= 90 
                and item.get("preferredZone") == zone
                and item.get("itemId") not in attempted_items
            ]
            
            if preferred_high_priority:
                for container in zone_containers:
                    placed, unplaced = await place_items_with_priority(container, preferred_high_priority)
                    placements.extend(placed)
                    
                    # Mark these items as attempted
                    for item in preferred_high_priority:
                        if any(p.itemId == item.get("itemId") for p in placed):
                            attempted_items.add(item.get("itemId"))
                    
                    # Update the list of items to exclude placed ones
                    preferred_high_priority = [
                        item for item in preferred_high_priority 
                        if item.get("itemId") not in attempted_items
                    ]
                    
                    if not preferred_high_priority:
                        break
        
        # Second pass: place standard-priority items in their preferred zones
        for zone, zone_containers in containers_by_zone.items():
            preferred_items = [
                item for item in sorted_items 
                if item.get("preferredZone") == zone
                and item.get("itemId") not in attempted_items
            ]
            
            if preferred_items:
                for container in zone_containers:
                    placed, unplaced = await place_items_with_priority(container, preferred_items)
                    placements.extend(placed)
                    
                    # Mark these items as attempted
                    for item in preferred_items:
                        if any(p.itemId == item.get("itemId") for p in placed):
                            attempted_items.add(item.get("itemId"))
                    
                    # Update the list of items to exclude placed ones
                    preferred_items = [
                        item for item in preferred_items 
                        if item.get("itemId") not in attempted_items
                    ]
                    
                    if not preferred_items:
                        break
        
        # Third pass: place remaining items in any zone (make multiple passes to ensure fair distribution)
        remaining_items = [
            item for item in sorted_items 
            if item.get("itemId") not in attempted_items
        ]
        
        if remaining_items:
            print(f"Trying to place {len(remaining_items)} items in any available container")
            
            # Multiple distribution passes to ensure all zones get items
            round_robin_zones = list(containers_by_zone.keys())
            
            # Keep attempting until we can't place any more items
            previous_remaining_count = len(remaining_items) + 1  # Initialize to ensure loop entry
            
            while remaining_items and len(remaining_items) < previous_remaining_count:
                previous_remaining_count = len(remaining_items)
                
                # Try each zone in round-robin fashion
                for zone in round_robin_zones:
                    if not remaining_items:
                        break
                        
                    zone_containers = containers_by_zone[zone]
                    
                    # Try each container in this zone
                    for container in zone_containers:
                        if not remaining_items:
                            break
                            
                        # Try to place a batch of items (limit to 10 at a time to ensure fair distribution)
                        current_batch = remaining_items[:10]
                        placed, unplaced = await place_items_with_priority(container, current_batch)
                        
                        if placed:
                            placements.extend(placed)
                            
                            # Remove placed items from remaining_items
                            placed_item_ids = {p.itemId for p in placed}
                            remaining_items = [
                                item for item in remaining_items 
                                if item.get("itemId") not in placed_item_ids
                            ]
                            
                            # Mark as attempted
                            for item_id in placed_item_ids:
                                attempted_items.add(item_id)
        
        # Any items still remaining are truly unplaceable
        unplaceable_items = [
            item for item in sorted_items 
            if item.get("itemId") not in {p.itemId for p in placements}
        ]
        
        print(f"Placed {len(placements)} items, {len(unplaceable_items)} items could not be placed")
        return placements, unplaceable_items
    except Exception as e:
        print(f"Error in place_all_items: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # Return empty lists to avoid further errors
        return [], items  # Return the original items list as unplaceable

async def save_placements(placements):
    """Save the item placements to the database"""
    try:
        # First, remove any existing placements for these items
        item_ids = []
        for p in placements:
            if isinstance(p, dict) and "itemId" in p:
                item_ids.append(p["itemId"])
            elif hasattr(p, "itemId"):
                item_ids.append(p.itemId)
        
        if item_ids:
            await placements_collection.delete_many({"itemId": {"$in": item_ids}})
        
        # Insert the new placements
        if placements:
            # Convert to dictionaries for MongoDB
            placement_dicts = []
            for placement in placements:
                # Check if placement is already a dict
                if isinstance(placement, dict):
                    placement_dicts.append(placement)
                else:
                    # Convert to dict if it's a Pydantic model
                    try:
                        placement_dicts.append(placement.dict())
                    except AttributeError:
                        # Handle case where dict() method doesn't exist
                        placement_dict = {
                            "itemId": placement.itemId,
                            "containerId": placement.containerId,
                            "position": placement.position.dict() if hasattr(placement.position, "dict") else placement.position
                        }
                        placement_dicts.append(placement_dict)
            
            if placement_dicts:
                await placements_collection.insert_many(placement_dicts)
        
        return True
    except Exception as e:
        print(f"Error in save_placements: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False