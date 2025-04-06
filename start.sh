#!/bin/bash

# Start the Docker daemon in the background
dockerd &

# Wait for Docker daemon to be ready
echo "Waiting for Docker daemon to start..."
while ! docker info >/dev/null 2>&1; do
  sleep 1
done
echo "Docker daemon started"

# Set Docker host to use the local Docker socket
export DOCKER_HOST=unix:///var/run/docker.sock

# Start the containers defined in docker-compose.yml
echo "Starting docker-compose services..."
docker-compose up

# Keep the container running if docker-compose exits
tail -f /dev/null