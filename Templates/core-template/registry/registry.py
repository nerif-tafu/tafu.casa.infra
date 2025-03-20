#!/usr/bin/env python3
import requests
import json
import time
import os
import yaml
import threading
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

RUNNER_IPS = [
    "192.168.3.215",  # Default runner
    "192.168.3.226"   # Staging runner
]
RUNNER_INFO_PATH = "/runner-info/json"  # Path to append to IP
OUTPUT_DIR = "/output"
POLLING_INTERVAL = 30  # seconds

# Global state
discovered_runners = []
last_updated = None

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html', 
                           runners=discovered_runners, 
                           last_updated=last_updated,
                           endpoints=[f"http://{ip}{RUNNER_INFO_PATH}" for ip in RUNNER_IPS])

@app.route('/api/runners')
def api_runners():
    return jsonify({
        "runners": discovered_runners,
        "last_updated": last_updated,
        "endpoints": [f"http://{ip}{RUNNER_INFO_PATH}" for ip in RUNNER_IPS]
    })

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
    
    for ip in RUNNER_IPS:
        endpoint = f"http://{ip}{RUNNER_INFO_PATH}"
        try:
            print(f"Trying to connect to {endpoint}...")
            response = requests.get(endpoint, timeout=5)
            print(f"Response from {endpoint}: status={response.status_code}")
            
            if response.status_code == 200:
                try:
                    print(f"Content from {endpoint}: {response.text[:200]}...")
                    runner_data = response.json()
                    
                    # Add the IP to the runner data
                    runner_data['ip'] = ip
                    
                    runners.append(runner_data)
                    print(f"Successfully parsed JSON from {endpoint}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON from {endpoint}: {e}")
                    print(f"Raw content: {response.text}")
            else:
                print(f"Error polling {endpoint}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error connecting to {endpoint}: {e}")
    
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
    
    # Create templates directory with absolute path
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    # Create HTML template - now with WebSocket support
    template_path = os.path.join(template_dir, 'index.html')
    if not os.path.exists(template_path) or True:  # Always update the template
        with open(template_path, 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Registry Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1, h2, h3 {
            color: #333;
        }
        .runner-card {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: #fff;
        }
        .service-list {
            margin-top: 10px;
        }
        .service-item {
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 5px;
        }
        .endpoint-list {
            margin-top: 20px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 4px;
        }
        .status {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            display: inline-block;
        }
        .status-success {
            background-color: #d4edda;
            color: #155724;
        }
        .status-error {
            background-color: #f8d7da;
            color: #721c24;
        }
        .refresh-btn {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        .refresh-btn:hover {
            background-color: #0069d9;
        }
        .last-updated {
            color: #6c757d;
            font-style: italic;
            margin-bottom: 20px;
        }
        /* Add new notification style */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #4CAF50;
            color: white;
            padding: 16px;
            border-radius: 4px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 1000;
        }
        
        .notification.show {
            opacity: 1;
        }
    </style>
    <!-- Add Socket.IO client library -->
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
    <div class="container">
        <h1>Traefik Registry Dashboard</h1>
        
        <div class="last-updated">
            Last updated: <span id="last-updated">{{ last_updated or 'Never' }}</span>
            <button class="refresh-btn" onclick="window.location.reload()">Refresh</button>
        </div>
        
        <h2>Monitored Endpoints</h2>
        <div class="endpoint-list">
            {% for endpoint in endpoints %}
                <div>{{ endpoint }}</div>
            {% endfor %}
        </div>
        
        <h2>Discovered Runners ({{ runners|length }})</h2>
        
        {% if runners %}
            {% for runner in runners %}
                <div class="runner-card">
                    <h3>
                        {{ runner.runner }} 
                        <span class="status status-success">Active</span>
                    </h3>
                    <div><strong>Domain:</strong> {{ runner.domain }}</div>
                    <div><strong>IP:</strong> {{ runner.ip }}</div>
                    
                    <div class="service-list">
                        <h4>Services</h4>
                        {% if runner.services %}
                            {% for service in runner.services %}
                                <div class="service-item">
                                    <div><strong>{{ service.name }}</strong></div>
                                    <div>Full Domain: {{ service.fullDomain }}</div>
                                </div>
                            {% endfor %}
                        {% else %}
                            <p>No services found.</p>
                        {% endif %}
                    </div>
                </div>
            {% endfor %}
        {% else %}
            <p>No runners discovered yet.</p>
        {% endif %}
    </div>
    
    <!-- Notification element -->
    <div id="notification" class="notification">Configuration updated! Refreshing...</div>
    
    <script>
        // Connect to WebSocket server
        const socket = io();
        
        // Listen for configuration updates
        socket.on('config_updated', function(data) {
            console.log('Configuration updated:', data);
            
            // Show notification
            const notification = document.getElementById('notification');
            notification.textContent = `Configuration updated at ${data.timestamp}! Refreshing...`;
            notification.classList.add('show');
            
            // Update last-updated time without refreshing
            document.getElementById('last-updated').textContent = data.timestamp;
            
            // Auto-refresh after a short delay
            setTimeout(function() {
                window.location.reload();
            }, 2000);
        });
    </script>
</body>
</html>
            """)
    
    # Start discovery in a background thread
    t = threading.Thread(target=discovery_thread, daemon=True)
    t.start()
    
    # Start the web server with WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    main() 