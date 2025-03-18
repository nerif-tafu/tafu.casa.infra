#!/bin/bash
set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# Get VM specs
read -p "Enter VM name: " VM_NAME
read -p "Enter number of CPU cores (default: 2): " CPU_CORES
read -p "Enter memory in GB (default: 4): " MEMORY_GB
read -p "Enter disk size in GB (default: 100): " DISK_GB

# Set defaults if empty
CPU_CORES=${CPU_CORES:-2}
MEMORY_GB=${MEMORY_GB:-4}
DISK_GB=${DISK_GB:-100}

# Create a profile for our server
cat <<EOF | lxc profile create "${VM_NAME}"
config:
  limits.cpu: "${CPU_CORES}"
  limits.memory: "${MEMORY_GB}GB"
  security.nesting: "true"
  security.syscalls.intercept.mknod: "true"
  security.syscalls.intercept.setxattr: "true"
description: Custom server profile for ${VM_NAME}
devices:
  config:
    source: cloud-init:config
    type: disk
  eth0:
    name: eth0
    network: macvlan
    type: nic
  root:
    path: /
    pool: default
    size: ${DISK_GB}GB
    type: disk
EOF

# Launch the VM with cloud-init config
lxc launch ubuntu:24.04 "${VM_NAME}" --profile "${VM_NAME}" --config=user.user-data="$(cat "${SCRIPT_DIR}/lxd-vm-base.yaml")"

# Wait for cloud-init to complete
echo "Waiting for cloud-init to complete..."
lxc exec "${VM_NAME}" -- cloud-init status --wait

echo "Setup complete! Your VM ${VM_NAME} is ready."
echo "You can connect to it using: lxc exec ${VM_NAME} bash"
echo "Or via SSH once you get its IP address: lxc list ${VM_NAME}" 