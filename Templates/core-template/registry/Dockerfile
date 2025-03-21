FROM python:3.10-alpine

WORKDIR /app

# Create data directory
RUN mkdir -p /app/data
RUN mkdir -p /app/templates
RUN mkdir -p /app/static

# Install required packages
RUN pip install --no-cache-dir requests pyyaml flask flask-socketio eventlet

# Copy application files
COPY *.py /app/
COPY templates/*.html /app/templates/

# We don't use static files yet, so we'll just create an empty directory
# Instead of COPY static/ /app/static/ 2>/dev/null || :

EXPOSE 5000

CMD ["python", "registry.py"] 