FROM python:3.10-alpine

WORKDIR /app

# Install required packages
RUN pip install --no-cache-dir requests pyyaml flask flask-socketio eventlet

COPY . /app/

EXPOSE 5000

CMD ["python", "registry.py"] 