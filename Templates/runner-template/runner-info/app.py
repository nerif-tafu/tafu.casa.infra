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
    """Discover running services on this runner"""
    global services, last_updated
    client = docker.from_env()
    
    try:
        all_containers = client.containers.list()
        discovered_services = []
        
        for container in all_containers:
            # Skip our own containers
            if 'bridge-traefik' in container.name or 'runner-info' in container.name:
                continue
                
            # Get container labels
            labels = container.labels
            
            # Process containers to extract service info
            name = container.name
            # Clean up the name by removing common suffixes
            for suffix in ['-1', '-traefik', '-frontend', '-backend']:
                if name.endswith(suffix):
                    name = name.replace(suffix, '')
            
            # Get the service domain from labels if available, otherwise construct it
            domain = f"{name}.{DOMAIN_FULL}"
            if 'traefik.http.routers' in str(labels):
                # Try to extract domain from traefik labels
                for label, value in labels.items():
                    if 'rule' in label and 'Host' in value:
                        try:
                            # Extract domain from Host rule
                            domain_part = value.split('Host(`')[1].split('`)')[0]
                            if domain_part:
                                domain = domain_part
                                break
                        except:
                            pass
            
            service_info = {
                "name": name,
                "fullDomain": domain,
                "container": container.name,
                "status": container.status
            }
            
            # Only add if we haven't already added this service
            if not any(s['name'] == name for s in discovered_services):
                discovered_services.append(service_info)
        
        # Update global state
        services = discovered_services
        last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        print(f"Error discovering services: {e}")

def discovery_thread():
    """Background thread that periodically discovers services"""
    while True:
        print("Discovering services...")
        discover_services()
        print(f"Found {len(services)} services")
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