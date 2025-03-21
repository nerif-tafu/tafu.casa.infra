#!/usr/bin/env python3
import os
import json
import time
import docker
import threading
import socket
from flask import Flask, jsonify, render_template_string

# Configuration
RUNNER_NAME = os.environ.get('RUNNER', 'default')
DOMAIN_FULL = os.environ.get('DOMAIN_FULL', 'preview.tafu.casa')
REFRESH_INTERVAL = 30  # seconds

# Global state
services = []
last_updated = None

app = Flask(__name__)

def get_template():
    """Read the HTML template from file"""
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    if os.path.exists(template_path):
        with open(template_path, 'r') as f:
            return f.read()

@app.route('/')
def index():
    """Serve the HTML view"""
    template = get_template()
    json_data = json.dumps(services, indent=2)
    return render_template_string(
        template,
        runner=RUNNER_NAME,
        domain=DOMAIN_FULL,
        last_updated=last_updated or "Never",
        services=services,
        json_data=json_data
    )

@app.route('/json')
def get_json():
    """Serve the JSON API"""
    runner_info = {
        "runner": RUNNER_NAME,
        "domain": DOMAIN_FULL,
        "services": services,
        "last_updated": last_updated
    }
    return jsonify(runner_info)

def discover_services():
    """Discover all services running in Docker with their domains."""
    discovered_services = []
    
    try:
        client = docker.from_env()
        containers = client.containers.list()
        
        # Filter for entry point containers using explicit labels
        for container in containers:
            labels = container.labels
            
            # Look for our service entry-point label
            if 'com.runner.service.name' in labels and 'com.runner.service.type' in labels:
                if labels['com.runner.service.type'] == 'entry-point':
                    service_name = labels['com.runner.service.name']
                    
                    # Get routing rule from traefik labels if available
                    domain = None
                    for label, value in labels.items():
                        if 'rule' in label and 'Host(' in value:
                            try:
                                # Extract domain from Host rule
                                domain = value.split('Host(`')[1].split('`)')[0]
                                break
                            except:
                                pass
                    
                    # Fallback to constructed domain if not found in labels
                    if not domain:
                        runner = os.environ.get('RUNNER', '')
                        domain_base = os.environ.get('DOMAIN_FULL', 'preview.tafu.casa')
                        if runner:
                            domain = f"{service_name}.{runner}.{domain_base}"
                        else:
                            domain = f"{service_name}.{domain_base}"
                        domain = domain.replace("..", ".")
                    
                    # Add service to discovered list
                    discovered_services.append({
                        "name": service_name,
                        "container": container.name,
                        "fullDomain": domain,
                        "status": container.status
                    })
        
        # Sort services by name for consistent display
        discovered_services.sort(key=lambda x: x["name"])
        
    except Exception as e:
        print(f"Error discovering services: {e}", flush=True)
    
    return discovered_services

def discovery_thread():
    """Background thread that periodically discovers services"""
    global services, last_updated
    while True:
        print("Discovering services...", flush=True)
        discovered = discover_services()
        services = discovered  # Update the global services variable
        last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Found {len(services)} services", flush=True)
        time.sleep(REFRESH_INTERVAL)

def main():
    # Create templates directory if it doesn't exist
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__))), exist_ok=True)
    
    # Start discovery in a background thread
    t = threading.Thread(target=discovery_thread, daemon=True)
    t.start()
    
    # Start the web server
    app.run(host='0.0.0.0', port=80)

if __name__ == "__main__":
    main() 