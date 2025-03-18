#!/bin/bash

# Check if we have a playbook URL as argument
if [ -z "$1" ]; then
    echo "Error: Playbook URL required"
    exit 1
fi

PLAYBOOK_URL=$1
PLAYBOOK_PATH="/tmp/setup-playbook.yml"

# Install Ansible if not present
if ! command -v ansible >/dev/null 2>&1; then
    apt-get update
    apt-get install -y software-properties-common
    apt-add-repository --yes --update ppa:ansible/ansible
    apt-get install -y ansible
fi

# Download the playbook
curl -s -o "$PLAYBOOK_PATH" "$PLAYBOOK_URL"

# Run the playbook
ansible-playbook "$PLAYBOOK_PATH" --connection=local --inventory localhost, --limit localhost

# Cleanup
rm "$PLAYBOOK_PATH"