# ISStow: International Space Station Storage Management API

ISStow is a backend and frontend application designed to manage item storage on the International Space Station. It provides an API built with FastAPI and a frontend served using Nginx.

---

## Project Structure


---

## Prerequisites

- Docker
- Docker Compose

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/alaotach/ISStow.git
cd ISStow
```
2. Build and Run the Application
Use Docker file to build and run the services:
```bash
docker build . 
```
3. Access the Application
Frontend: Open your browser and navigate to http://localhost.
Backend API: Access the API documentation at http://localhost:8000/docs

Services
1. MongoDB
Image: mongo:latest
Port: 27017
Environment Variables:
MONGO_INITDB_ROOT_USERNAME: MongoDB root username
MONGO_INITDB_ROOT_PASSWORD: MongoDB root password
2. Backend (FastAPI)
Build Context: ./extracted_code
Port: 8000
Environment Variables:
MONGODB_URI: MongoDB connection string
MONGODB_DB_NAME: MongoDB database name
3. Frontend (Nginx)
Build Context: ./frontend-code
Port: 80


Backend API
The backend is built with FastAPI and provides the following features:

Routes:
/ - Root endpoint
/placement - Placement management
/search - Search functionality
/waste - Waste management
/simulation - Simulation tools
/import_export - Import/export data
/logs - Logs management
/containers - Container management
/items - Item management
Database: MongoDB with collections for items, containers, placements, logs, waste, and simulations.

Frontend
The frontend is a static web application built with Vite + React + TypeScript. It is served using Nginx.

Environment Variables
The following environment variables are used in the project:

Backend
MONGODB_URI: MongoDB connection string (default: mongodb://localhost:27017)
MONGODB_DB_NAME: MongoDB database name (default: isstow)
Deployment
To deploy the application, ensure Docker and Docker Compose are installed on the target server. Then, run:

```bash
docker-compose up --build -d
```
