#!/usr/bin/env python3
import os
import json
import time
import docker
import threading
import socket
import requests
import yaml
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

def get_container_ip(container_name):
    """Get the IP address of a container on the bridge network"""
    try:
        # Use Docker API to get container details
        client = docker.from_env()
        container = client.containers.get(container_name)
        
        # Look for the bridge-network IP
        networks = container.attrs["NetworkSettings"]["Networks"]
        for network_name, network_config in networks.items():
            if network_name == "bridge-network":
                return network_config["IPAddress"]
        
        # If no bridge-network IP found, return the first IP
        if networks:
            return list(networks.values())[0]["IPAddress"]
        
        return None
    except Exception as e:
        print(f"Error getting container IP for {container_name}: {e}", flush=True)
        return None

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
                    
                    # Check if we found domain in labels
                    if domain:
                        # If domain already contains the service name, don't duplicate it
                        if domain.startswith(f"{service_name}."):
                            full_domain = domain
                        else:
                            full_domain = f"{service_name}.{domain}"
                    else:
                        # Fallback to constructed domain if not found in labels
                        runner = os.environ.get('RUNNER', '')
                        domain_base = os.environ.get('DOMAIN_FULL', 'preview.tafu.casa')
                        if runner:
                            domain = f"{runner}.{domain_base}"
                        else:
                            domain = domain_base
                        domain = domain.replace("..", ".")
                        full_domain = f"{service_name}.{domain}"
                    
                    # Make sure the Host rule in bridge traefik includes the complete domain
                    router_rule = f"Host(`{full_domain}`)"
                    
                    # Add service to discovered list
                    discovered_services.append({
                        "name": service_name,
                        "container": container.name,
                        "fullDomain": full_domain,
                        "status": container.status,
                        "routerRule": router_rule,
                        "debug": {
                            "labels": {key: value for key, value in labels.items() if "traefik" in key},
                            "originalDomain": domain,
                            "networks": [net for net in container.attrs["NetworkSettings"]["Networks"]]
                        }
                    })
        
        # Sort services by name for consistent display
        discovered_services.sort(key=lambda x: x["name"])
        
    except Exception as e:
        print(f"Error discovering services: {e}", flush=True)
    
    return discovered_services

def register_services_with_traefik(services):
    """Register discovered services with the Traefik REST provider"""
    try:
        # Create router configurations for each service
        dynamic_config = {
            "http": {
                "routers": {},
                "services": {}
            }
        }
        
        for service in services:
            service_name = service["name"]
            service_domain = service["fullDomain"]
            service_ip = get_container_ip(service["container"])
            
            print(f"Container {service['container']} has IP: {service_ip}", flush=True)
            
            # Skip if we couldn't get the IP
            if not service_ip:
                print(f"Skipping {service_name} - could not get IP", flush=True)
                continue
                
            router_name = f"auto-{service_name}"
            
            # Create router for this service
            dynamic_config["http"]["routers"][router_name] = {
                "rule": f"Host(`{service_domain}`)",
                "service": router_name,
                "entryPoints": ["web"]
            }
            
            # Create service pointing to the container
            dynamic_config["http"]["services"][router_name] = {
                "loadBalancer": {
                    "servers": [{"url": f"http://{service_ip}:80"}]
                }
            }
        
        # Post to Traefik REST provider
        traefik_url = "http://traefik:8080/api/providers/rest"
        print(f"Sending config to Traefik: {json.dumps(dynamic_config)}", flush=True)
        response = requests.put(traefik_url, json=dynamic_config)
        print(f"Traefik API response: {response.status_code} {response.text}", flush=True)
        
    except Exception as e:
        print(f"Error registering services: {e}", flush=True)

def check_traefik_status():
    """Check Traefik status and available routers/services"""
    try:
        # Try to get Traefik API status
        response = requests.get("http://traefik:8080/api/http/routers")
        if response.status_code == 200:
            routers = response.json()
            print(f"Traefik has {len(routers)} routers configured", flush=True)
            for router in routers:
                print(f"Router: {router['name']}, Rule: {router['rule']}", flush=True)
        else:
            print(f"Could not get Traefik routers: {response.status_code}", flush=True)
    except Exception as e:
        print(f"Error checking Traefik status: {e}", flush=True)

def discovery_thread():
    """Background thread that periodically discovers services"""
    global services, last_updated
    while True:
        print("Discovering services...", flush=True)
        discovered = discover_services()
        services = discovered
        last_updated = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"Found {len(services)} services", flush=True)
        # Generate dynamic configuration file based on discovered services
        generate_traefik_config(services)
        # Register discovered services with Traefik
        register_services_with_traefik(services)
        # Check Traefik status for debugging
        check_traefik_status()
        time.sleep(REFRESH_INTERVAL)

def generate_traefik_config(services):
    """Generate Traefik dynamic configuration file from discovered services"""
    try:
        # Create base config structure
        config = {
            "http": {
                "routers": {},
                "services": {}
            }
        }
        
        # Add a router and service for each discovered service
        for service in services:
            name = service["name"]
            domain = service["fullDomain"]
            container = service["container"]
            
            # Skip containers that aren't running
            if service["status"] != "running":
                continue
            
            # Get the container IP directly
            service_ip = get_container_ip(container)
            if not service_ip:
                print(f"Skipping {name} - could not get IP", flush=True)
                continue
            
            # Create router for this service
            router_name = f"auto-{name}"
            config["http"]["routers"][router_name] = {
                "rule": f"Host(`{domain}`)",
                "service": router_name,
                "entryPoints": ["web"],
                "priority": 100
            }
            
            # Create service pointing to the container
            config["http"]["services"][router_name] = {
                "loadBalancer": {
                    "servers": [{"url": f"http://{service_ip}:80"}],
                    "passHostHeader": True
                }
            }
        
        # Write config to file
        config_path = "/etc/traefik/dynamic/services-generated.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Generated Traefik config with {len(services)} services at {config_path}", flush=True)
        print(f"Configuration details: {json.dumps(config, indent=2)}", flush=True)
    except Exception as e:
        print(f"Error generating Traefik config: {e}", flush=True)

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