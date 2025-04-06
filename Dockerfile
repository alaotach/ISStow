FROM docker:23-dind

# Install docker-compose and other necessary tools
RUN apk add --no-cache \
    docker-compose \
    bash \
    curl

# Create a directory for the application
WORKDIR /app

# Copy docker-compose.yml and any other necessary files
COPY docker-compose.yml .
COPY extracted_code ./extracted_code
COPY frontend-code ./frontend-code
COPY start.sh .

# Make sure the script is executable
RUN chmod +x /app/start.sh

# Expose the necessary ports
EXPOSE 80 8000 27017

# Set environment variable for Docker daemon
ENV DOCKER_TLS_CERTDIR=""
ENV DOCKER_HOST=unix:///var/run/docker.sock

# Run the startup script when the container starts
CMD ["/app/start.sh"]