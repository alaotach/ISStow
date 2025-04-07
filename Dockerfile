# Use Ubuntu 20.04 instead of 22.04 to avoid libssl1.1 compatibility issues with MongoDB
FROM ubuntu:20.04

# Set environment variables to avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Update package lists and install common dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    gnupg \
    curl \
    apt-transport-https \
    ca-certificates \
    python3-pip \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Python 3.9 from deadsnakes PPA
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.9 \
    python3.9-venv \
    python3.9-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links to make Python 3.9 the default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1 && \
    update-alternatives --set python3 /usr/bin/python3.9

# Install MongoDB 4.4 (compatible with Ubuntu 20.04)
RUN wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add - && \
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list && \
    apt-get update && \
    apt-get install -y mongodb-org && \
    mkdir -p /data/db && \
    mkdir -p /var/log/mongodb && \
    chown -R mongodb:mongodb /data/db /var/log/mongodb && \
    rm -rf /var/lib/apt/lists/*

# Install Nginx
RUN apt-get update && \
    apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment
RUN python3.9 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install pip tools in the virtual environment
RUN /opt/venv/bin/pip install --upgrade pip setuptools wheel

# Create app directory and set as working directory
WORKDIR /app

# Copy application files
COPY . /app/

# Install Python dependencies if requirements.txt exists
RUN if [ -f requirements.txt ]; then \
        /opt/venv/bin/pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt found. Skipping pip install."; \
    fi

# Install gunicorn in the virtual environment
RUN /opt/venv/bin/pip install gunicorn

# Configure Nginx
RUN echo 'server {\n\
    listen 80;\n\
    server_name localhost;\n\
    \n\
    location / {\n\
        proxy_pass http://127.0.0.1:8000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
    }\n\
}' > /etc/nginx/sites-available/default

# Create MongoDB configuration file
RUN echo 'storage:\n\
  dbPath: /data/db\n\
net:\n\
  bindIp: 127.0.0.1\n\
  port: 27017\n\
systemLog:\n\
  destination: file\n\
  path: /var/log/mongodb/mongod.log\n\
  logAppend: true' > /etc/mongod.conf

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Starting services - $(date)"\n\
\n\
# Start MongoDB\n\
echo "Starting MongoDB..."\n\
mongod --config /etc/mongod.conf --fork\n\
\n\
# Start Python application\n\
echo "Starting Python application..."\n\
if [ -f /app/app.py ]; then\n\
    /opt/venv/bin/gunicorn --bind 0.0.0.0:8000 app:app &\n\
elif [ -f /app/wsgi.py ]; then\n\
    /opt/venv/bin/gunicorn --bind 0.0.0.0:8000 wsgi:application &\n\
elif [ -f /app/manage.py ]; then\n\
    cd /app && /opt/venv/bin/python manage.py runserver 0.0.0.0:8000 &\n\
else\n\
    echo "No recognized Python web application entry point found."\n\
fi\n\
\n\
# Start Nginx\n\
echo "Starting Nginx..."\n\
nginx -g "daemon off;"\n\
' > /start.sh && chmod +x /start.sh

# Expose ports
EXPOSE 80 27017

# Define volume for MongoDB data
VOLUME ["/data/db"]

# Run startup script
CMD ["/start.sh"]
