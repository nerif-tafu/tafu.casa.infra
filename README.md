# tafu.casa.infra

Infrastructure setup and templates for tafu.casa services.

## Project Structure

- Bases: LXD host configurations and setup scripts
- Templates: VM configuration templates
- Services: Example service configurations

## LXD Host Setup

### 1. Bootstrap LXD Host
First, set up the LXD host with btrfs storage and macvlan networking:

    sudo ./Bases/lxd-vm-base/bootstrap.sh

### 2. Create a VM
Create a new VM with custom specifications:

    sudo ./Bases/lxd-vm-base/create-vm.sh

You'll be prompted for:
- VM name
- Number of CPU cores
- Memory size (GB)
- Disk size (GB)

The VM will be created with:
- Ubuntu 24.04
- finn-rm user with sudo access
- SSH key imported from Launchpad
- Direct network access via macvlan
- Nested virtualization support
- Docker-compatible syscall handling

### 3. Connect to your VM

    # Get VM IP address
    lxc list

    # SSH into the VM
    ssh finn-rm@<vm-ip>

## Service Example: Demo App

The demo app in Services/demo-app-service shows a basic setup with:
- Frontend server (port 9000)
- Backend API (port 9001)
- Traefik reverse proxy (ports 443 and 8080)

To deploy the demo app:

    cd Services/demo-app-service
    docker compose up -d

Access the services at:
- Frontend: http://<vm-ip>/
- Backend API: http://<vm-ip>/api/health
- Traefik Dashboard: http://<vm-ip>:8080