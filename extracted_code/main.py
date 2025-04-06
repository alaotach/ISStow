from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from routes import placement, search, waste, simulation, import_export, logs, containers, items

app = FastAPI(
    title="ISStow API",
    description="API for managing item storage on the International Space Station",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all the routes
app.include_router(placement.router)  # Removed prefix since routers have their own prefixes
app.include_router(search.router)
app.include_router(waste.router)
app.include_router(simulation.router)
app.include_router(import_export.router)
app.include_router(logs.router)
app.include_router(containers.router)  # Add containers route
app.include_router(items.router)       # Add items route

@app.get("/")
async def root():
    return {"message": "Welcome to ISStow API"}

# Run the application when this file is executed directly
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)