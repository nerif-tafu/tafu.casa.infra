#!/bin/bash
set -e  # Exit on any error

# Check if we have a playbook URL as argument
if [ -z "$1" ]; then
    echo "Error: Playbook URL required"
    exit 1
fi

PLAYBOOK_URL=$1
PLAYBOOK_PATH="/tmp/setup-playbook.yml"

# Install initial requirements
apt-get update
apt-get install -y software-properties-common ansible ssh-import-id

# Create finn-rm user and set up initial access
useradd -m -s /bin/bash finn-rm
usermod -aG sudo finn-rm
echo "finn-rm ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/finn-rm
chmod 0440 /etc/sudoers.d/finn-rm

# Import SSH key for finn-rm
sudo -u finn-rm ssh-import-id-lp finn-rm

# Download the playbook
curl -s -o "$PLAYBOOK_PATH" "$PLAYBOOK_URL"

# Switch to finn-rm user and run the playbook
sudo -u finn-rm ansible-playbook "$PLAYBOOK_PATH" --connection=local --inventory localhost, --limit localhost

# Cleanup playbook
rm "$PLAYBOOK_PATH"

# If we're the ubuntu user, remove it
if [ "$(whoami)" = "ubuntu" ]; then
    echo "Removing ubuntu user..."
    # Create a self-deleting script
    cat > /tmp/remove-ubuntu.sh << 'EOF'
#!/bin/bash
sleep 2  # Give parent process time to exit
deluser --remove-home ubuntu
rm -- "$0"  # Self delete this script
EOF
    chmod +x /tmp/remove-ubuntu.sh
    # Run the cleanup script in the background and exit
    nohup /tmp/remove-ubuntu.sh >/dev/null 2>&1 &
fi