FROM python:3.10-alpine

WORKDIR /app

# Install dependencies
RUN pip install requests pyyaml flask

# Create template directory
RUN mkdir -p /app/templates

# Copy application files
COPY registry.py /app/
RUN chmod +x /app/registry.py

# Run the application
CMD ["/app/registry.py"] 