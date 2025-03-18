# Demo App & Server Setup

## Quick Start
To set up a new server, first ensure you have `curl` and `jq` installed:
```bash
sudo apt update && sudo apt install -y curl jq
```

Then run:
```bash
curl -s https://raw.githubusercontent.com/finn-rm/tafu.casa.infra/main/scripts/setup.sh | sudo bash -s -- $(curl -s https://api.github.com/repos/finn-rm/tafu.casa.infra/contents/playbooks/standard-server-setup.yml | jq -r '.download_url')
```