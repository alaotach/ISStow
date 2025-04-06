from fastapi import APIRouter, Depends, HTTPException, status
from models.waste import (
    WasteIdentifyResponse, ReturnPlanRequest, ReturnPlanResponse, 
    UndockingRequest, UndockingResponse, ReturnPlanStep,
    RetrievalStep, ReturnManifest
)
from services.waste import identify_waste_items, prepare_return_plan, complete_undocking
from database import logs_collection
from datetime import datetime

router = APIRouter()

@router.get("/waste/identify", response_model=WasteIdentifyResponse)
async def identify_waste():
    """Identify items that should be considered waste (expired or used up)"""
    waste_items = await identify_waste_items()
    
    # Log the waste identification
    await logs_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "actionType": "waste_identification",
        "details": {
            "wasteItemsCount": len(waste_items),
            "wasteItemsIds": [item.itemId for item in waste_items]
        }
    })
    
    return WasteIdentifyResponse(
        success=True,
        wasteItems=waste_items
    )

@router.post("/waste/return-plan", response_model=ReturnPlanResponse)
async def create_return_plan(request: ReturnPlanRequest):
    """Create a plan for returning waste items to Earth"""
    return_plan, retrieval_steps, return_manifest = await prepare_return_plan(
        request.undockingContainerId,
        request.undockingDate,
        request.maxWeight
    )
    
    if not return_manifest:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Container {request.undockingContainerId} not found"
        )
    
    # Log the return plan creation
    await logs_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "actionType": "return_plan_creation",
        "details": {
            "undockingContainerId": request.undockingContainerId,
            "undockingDate": request.undockingDate,
            "itemsCount": len(return_manifest["returnItems"]),
            "totalWeight": return_manifest["totalWeight"]
        }
    })
    
    # Convert return_plan to the correct format
    formatted_return_plan = [
        ReturnPlanStep(
            step=step["step"],
            itemId=step["itemId"],
            itemName=step["itemName"],
            fromContainer=step["fromContainer"],
            toContainer=step["toContainer"]
        ) for step in return_plan
    ]
    
    # Convert retrieval_steps to the correct format
    formatted_retrieval_steps = [
        RetrievalStep(
            step=step["step"],
            action=step["action"],
            itemId=step["itemId"],
            itemName=step["itemName"]
        ) for step in retrieval_steps
    ]
    
    # Create the return manifest
    formatted_manifest = ReturnManifest(
        undockingContainerId=return_manifest["undockingContainerId"],
        undockingDate=return_manifest["undockingDate"],
        returnItems=return_manifest["returnItems"],
        totalVolume=return_manifest["totalVolume"],
        totalWeight=return_manifest["totalWeight"]
    )
    
    return ReturnPlanResponse(
        success=True,
        returnPlan=formatted_return_plan,
        retrievalSteps=formatted_retrieval_steps,
        returnManifest=formatted_manifest
    )

@router.post("/waste/complete-undocking", response_model=UndockingResponse)
async def mark_undocking_complete(request: UndockingRequest):
    """Mark an undocking as complete and remove items from inventory"""
    success, items_removed = await complete_undocking(request.undockingContainerId)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No pending return manifest found for container {request.undockingContainerId}"
        )
    
    # Log the undocking completion
    await logs_collection.insert_one({
        "timestamp": datetime.utcnow(),
        "actionType": "undocking_completion",
        "details": {
            "undockingContainerId": request.undockingContainerId,
            "itemsRemoved": items_removed
        }
    })
    
    return UndockingResponse(
        success=True,
        itemsRemoved=items_removed
    )