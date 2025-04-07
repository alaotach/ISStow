FROM nxtcybernet127/isshack:latest

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create custom Nginx configuration for frontend
RUN echo 'server {\n\
    listen 80;\n\
    server_name localhost;\n\
    \n\
    # API requests\n\
    location /api/ {\n\
        proxy_pass http://127.0.0.1:9000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
    }\n\
    \n\
    # Static frontend files\n\
    location / {\n\
        root /usr/share/nginx/html;\n\
        index index.html index.htm;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}' > /etc/nginx/sites-available/default

# Make sure frontend directory exists
RUN mkdir -p /usr/share/nginx/html

# Copy frontend code to Nginx web root
COPY ./frontend-code/ /usr/share/nginx/html/

# Make sure frontend files are readable by Nginx
RUN chown -R www-data:www-data /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Update MongoDB configuration to listen on all interfaces
RUN echo 'storage:\n\
  dbPath: /data/db\n\
net:\n\
  bindIp: 0.0.0.0\n\
  port: 27017\n\
systemLog:\n\
  destination: file\n\
  path: /var/log/mongodb/mongod.log\n\
  logAppend: true' > /etc/mongod.conf

# Create a custom startup script that adds your application
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Starting services - $(date)"\n\
\n\
# Make sure MongoDB directories exist with proper permissions\n\
mkdir -p /data/db /var/log/mongodb\n\
chown -R mongodb:mongodb /data/db /var/log/mongodb\n\
chmod 755 /data/db /var/log/mongodb\n\
\n\
# Start MongoDB\n\
echo "Starting MongoDB..."\n\
mongod --config /etc/mongod.conf --fork\n\
\n\
# Verify MongoDB is running\n\
echo "Waiting for MongoDB to start..."\n\
sleep 3\n\
if pgrep -x "mongod" > /dev/null; then\n\
    echo "MongoDB is running!"\n\
    mongo --eval "db.adminCommand(\"ping\")" || echo "MongoDB ping failed"\n\
else\n\
    echo "MongoDB failed to start!"\n\
    cat /var/log/mongodb/mongod.log\n\
    exit 1\n\
fi\n\
\n\
# Start Python application\n\
echo "Starting custom Python application..."\n\
cd /app && /opt/venv/bin/python /app/extracted_code/main.py &\n\
\n\
# Verify frontend files exist\n\
echo "Checking frontend files..."\n\
ls -la /usr/share/nginx/html\n\
\n\
# Start Nginx\n\
echo "Starting Nginx..."\n\
nginx -g "daemon off;"\n\
' > /custom_start.sh && chmod +x /custom_start.sh

# Expose the required ports
EXPOSE 80 27017 9000

# Use the custom startup script
CMD ["/custom_start.sh"]
