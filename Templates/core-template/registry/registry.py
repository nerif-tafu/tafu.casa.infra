#!/usr/bin/env python3
import requests
import json
import time
import os
import yaml
import threading
import uuid
from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_socketio import SocketIO

# Read domain from environment or use default
DOMAIN_BASE = os.environ.get('DOMAIN_BASE', 'preview.tafu.casa')

# File to store endpoints
ENDPOINTS_FILE = "/app/data/endpoints.json"
OUTPUT_DIR = "/output"
POLLING_INTERVAL = 30  # seconds

# Ensure data directory exists
os.makedirs(os.path.dirname(ENDPOINTS_FILE), exist_ok=True)

# Default endpoints if file doesn't exist
DEFAULT_ENDPOINTS = [
    {"id": str(uuid.uuid4()), "ip": "192.168.3.215", "description": "Default runner"},
    {"id": str(uuid.uuid4()), "ip": "192.168.3.226", "description": "Staging runner"}
]

# Global state
discovered_runners = []
last_updated = None

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Load endpoints from file or use defaults
def load_endpoints():
    try:
        if os.path.exists(ENDPOINTS_FILE):
            with open(ENDPOINTS_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create file with defaults
            save_endpoints(DEFAULT_ENDPOINTS)
            return DEFAULT_ENDPOINTS
    except Exception as e:
        print(f"Error loading endpoints: {e}")
        return DEFAULT_ENDPOINTS

# Save endpoints to file
def save_endpoints(endpoints):
    try:
        os.makedirs(os.path.dirname(ENDPOINTS_FILE), exist_ok=True)
        with open(ENDPOINTS_FILE, 'w') as f:
            json.dump(endpoints, f, indent=2)
    except Exception as e:
        print(f"Error saving endpoints: {e}")

@app.route('/')
def index():
    endpoints = load_endpoints()
    return render_template('index.html', 
                           runners=discovered_runners, 
                           last_updated=last_updated,
                           endpoints=endpoints)

@app.route('/endpoints')
def endpoints_page():
    endpoints = load_endpoints()
    return render_template('endpoints.html', endpoints=endpoints)

@app.route('/endpoints/add', methods=['POST'])
def add_endpoint():
    ip = request.form.get('ip', '').strip()
    description = request.form.get('description', '').strip()
    
    if not ip:
        return jsonify({"status": "error", "message": "IP address is required"}), 400
    
    endpoints = load_endpoints()
    endpoints.append({
        "id": str(uuid.uuid4()),
        "ip": ip,
        "description": description
    })
    
    save_endpoints(endpoints)
    socketio.emit('endpoints_updated')
    
    # Trigger an immediate refresh of runner discovery
    threading.Thread(target=lambda: refresh_config()).start()
    
    return redirect('/endpoints')

@app.route('/endpoints/delete/<endpoint_id>', methods=['POST'])
def delete_endpoint(endpoint_id):
    endpoints = load_endpoints()
    endpoints = [e for e in endpoints if e.get('id') != endpoint_id]
    save_endpoints(endpoints)
    socketio.emit('endpoints_updated')
    
    # Trigger an immediate refresh of runner discovery
    threading.Thread(target=lambda: refresh_config()).start()
    
    return redirect('/endpoints')

@app.route('/endpoints/edit/<endpoint_id>', methods=['POST'])
def edit_endpoint(endpoint_id):
    ip = request.form.get('ip', '').strip()
    description = request.form.get('description', '').strip()
    
    if not ip:
        return jsonify({"status": "error", "message": "IP address is required"}), 400
    
    endpoints = load_endpoints()
    for endpoint in endpoints:
        if endpoint.get('id') == endpoint_id:
            endpoint['ip'] = ip
            endpoint['description'] = description
            break
    
    save_endpoints(endpoints)
    socketio.emit('endpoints_updated')
    
    # Trigger an immediate refresh of runner discovery
    threading.Thread(target=lambda: refresh_config()).start()
    
    return redirect('/endpoints')

@app.route('/api/runners')
def api_runners():
    return jsonify({
        "runners": discovered_runners,
        "last_updated": last_updated,
        "endpoints": [e['ip'] for e in load_endpoints()]
    })

@app.route('/api/endpoints')
def api_endpoints():
    return jsonify(load_endpoints())

@app.route('/api/refresh', methods=['GET', 'POST'])
def refresh_config():
    """Webhook endpoint to trigger immediate refresh"""
    print("Refresh webhook triggered")
    
    # Run discovery and generate config synchronously
    runners = discover_runners()
    generate_config(runners)
    
    # Notify all connected clients of the update
    socketio.emit('config_updated', {
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'runner_count': len(runners)
    })
    
    return jsonify({
        "status": "success",
        "message": "Configuration refresh triggered",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "services_count": len(runners)
    })

def discover_runners():
    global discovered_runners, last_updated
    runners = []
    
    endpoints = load_endpoints()
    
    for endpoint in endpoints:
        ip = endpoint['ip']
        endpoint_url = f"http://{ip}/runner-info/json"
        try:
            print(f"Trying to connect to {endpoint_url}...")
            response = requests.get(endpoint_url, timeout=5)
            print(f"Response from {endpoint_url}: status={response.status_code}")
            
            if response.status_code == 200:
                try:
                    print(f"Content from {endpoint_url}: {response.text[:200]}...")
                    runner_data = response.json()
                    
                    # Add the IP to the runner data
                    runner_data['ip'] = ip
                    
                    runners.append(runner_data)
                    print(f"Successfully parsed JSON from {endpoint_url}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON from {endpoint_url}: {e}")
                    print(f"Raw content: {response.text}")
            else:
                print(f"Error polling {endpoint_url}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error connecting to {endpoint_url}: {e}")
    
    # Update global state
    discovered_runners = runners
    last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
    
    return runners

def generate_config(runners):
    # Start with an empty configuration structure
    config = {
        "http": {
            "routers": {},
            "services": {}
        }
    }
    
    # For each runner
    for runner in runners:
        runner_name = runner['runner']  # Either 'default' or 'staging' or other name
        runner_ip = runner['ip']
        
        # For each service on this runner
        if 'services' in runner and runner['services']:
            for service in runner['services']:
                service_name = service['name']
                service_domain = service['fullDomain']
                
                # Create unique router and service names using both runner and service name
                # This prevents services with the same name on different runners from overwriting each other
                router_name = f"{service_name}-{runner_name}-router"
                service_backend_name = f"{service_name}-{runner_name}-service"
                
                # Create router for this specific service
                config["http"]["routers"][router_name] = {
                    "rule": f"Host(`{service_domain}`)",
                    "service": service_backend_name,
                    "entryPoints": ["websecure", "web"]
                }
                
                # Create service for this specific service
                config["http"]["services"][service_backend_name] = {
                    "loadBalancer": {
                        "servers": [{"url": f"http://{runner_ip}:80"}]
                    }
                }
                
                print(f"Added route for {service_domain} to {runner_ip}")
    
    # Write the combined configuration to a single file
    output_file = os.path.join(OUTPUT_DIR, "services.yml")
    with open(output_file, 'w') as f:
        yaml.dump(config, f)
    print(f"Generated configuration with {len(config['http']['routers'])} service routes")

def discovery_thread():
    while True:
        print("Discovering runners...")
        runners = discover_runners()
        print(f"Found {len(runners)} runners")
        
        generate_config(runners)
        
        # Notify all connected clients of the update
        socketio.emit('config_updated', {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'runner_count': len(runners)
        })
        
        time.sleep(POLLING_INTERVAL)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Don't generate templates dynamically
    # Just use the external templates provided
    
    # Start discovery in a background thread
    t = threading.Thread(target=discovery_thread, daemon=True)
    t.start()
    
    # Start the web server with WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    main() 