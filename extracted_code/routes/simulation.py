from fastapi import APIRouter, HTTPException, Query
from models.simulation import SimulationRequest, SimulationResponse
from services.simulation import advance_simulation_time, reset_simulation, get_simulation_history, get_current_simulation_date
from typing import Optional, List
from datetime import datetime

router = APIRouter(
    prefix="/api/simulate",
    tags=["Simulation"]
)

@router.post("/day", response_model=SimulationResponse)
async def simulate_day(request: SimulationRequest):
    """
    Simulate the passage of time and item usage
    
    Parameters:
    - numOfDays: Number of days to simulate
    - toTimestamp: ISO timestamp to simulate to (instead of numOfDays)
    - itemsToBeUsedPerDay: List of items to be used each day
    
    Returns: SimulationResponse with changes that occurred
    """
    try:
        # Validate request
        if request.numOfDays is not None and request.numOfDays <= 0:
            raise HTTPException(status_code=400, detail="Number of days must be positive")
        
        if request.toTimestamp and request.numOfDays:
            raise HTTPException(status_code=400, detail="Provide either numOfDays or toTimestamp, not both")
            
        # Process simulation
        result = await advance_simulation_time(
            days=request.numOfDays,
            to_timestamp=request.toTimestamp,
            items_to_use=[item.dict() for item in request.itemsToBeUsedPerDay]
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during simulation: {str(e)}")

@router.post("/reset")
async def reset_simulation_time():
    """
    Reset the simulation date to the current date
    """
    try:
        result = await reset_simulation()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting simulation: {str(e)}")

@router.get("/history")
async def get_simulation_logs(limit: int = Query(10, ge=1, le=100)):
    """
    Get history of simulation runs
    
    Parameters:
    - limit: Maximum number of history entries to return (1-100)
    """
    try:
        logs = await get_simulation_history(limit)
        return {"success": True, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching simulation history: {str(e)}")

@router.get("/current-date")
async def get_current_date():
    """
    Get the current simulation date
    """
    try:
        current_date = await get_current_simulation_date()
        return {
            "success": True,
            "currentDate": current_date.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching current simulation date: {str(e)}")