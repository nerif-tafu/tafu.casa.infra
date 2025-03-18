#!/bin/bash
set -e  # Exit on any error

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Install LXD if not present
if ! command -v lxd >/dev/null 2>&1; then
    apt-get update
    apt-get install -y snapd
    snap install lxd
fi

# Initialize LXD if not already initialized
if ! lxc storage list >/dev/null 2>&1; then
    # Check if we have a btrfs partition
    if ! mountpoint -q /var/lib/lxd; then
        # Create a btrfs partition if we have free space
        FREE_DEVICE=$(lsblk -ln -o NAME,TYPE,FSTYPE,MOUNTPOINT | awk '$2=="disk" && $3=="" && $4=="" {print $1}' | head -1)
        if [ -n "$FREE_DEVICE" ]; then
            mkfs.btrfs "/dev/${FREE_DEVICE}"
            mkdir -p /var/lib/lxd
            mount "/dev/${FREE_DEVICE}" /var/lib/lxd
            echo "/dev/${FREE_DEVICE} /var/lib/lxd btrfs defaults 0 0" >> /etc/fstab
        fi
    fi

    # Initialize LXD
    cat <<EOF | lxd init --preseed
config:
  core.https_address: '[::]:8443'
  core.trust_password: $(openssl rand -base64 32)
networks:
- config:
    ipv4.address: auto
    ipv6.address: auto
  description: ""
  name: lxdbr0
  type: bridge
storage_pools:
- config:
    source: /var/lib/lxd
  description: ""
  name: default
  driver: btrfs
profiles:
- config: {}
  description: ""
  devices:
    eth0:
      name: eth0
      network: lxdbr0
      type: nic
    root:
      path: /
      pool: default
      type: disk
  name: default
EOF
fi

# Setup macvlan network if not exists
if ! lxc network show macvlan >/dev/null 2>&1; then
    # Get the main interface
    MAIN_IF=$(ip route | grep default | awk '{print $5}')
    
    lxc network create macvlan \
        type=macvlan \
        parent="${MAIN_IF}"
fi

echo "LXD host setup complete with btrfs storage and macvlan network!" 