from fastapi import APIRouter, HTTPException
from database import containers_collection
from models.container import ContainerPlacement
from typing import List

router = APIRouter(
    prefix="/containers",
    tags=["Containers"]
)

@router.get("/", response_model=List[ContainerPlacement])
async def get_containers():
    """
    Retrieve all containers.
    """
    try:
        containers = await containers_collection.find().to_list(length=None)
        if not containers:
            raise HTTPException(status_code=404, detail="No containers found")
        return containers
    except Exception as e:
        print(f"Error fetching containers: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching containers")

@router.get("/{container_id}", response_model=ContainerPlacement)
async def get_container(container_id: str):
    """
    Retrieve a specific container by its ID.
    """
    try:
        container = await containers_collection.find_one({"containerId": container_id})
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        return container
    except Exception as e:
        print(f"Error fetching container {container_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching container")
