# Demo App & Server Setup

## Quick Start
To set up a new server, first ensure you have `curl` and `jq` installed:
```bash
sudo apt update && sudo apt install -y curl jq
```

Then run:
```bash
curl -s https://raw.githubusercontent.com/nerif-tafu/tafu.casa.infra/main/scripts/setup.sh | sudo bash -s -- $(curl -s https://api.github.com/repos/nerif-tafu/tafu.casa.infra/contents/playbooks/standard-server-setup.yml | jq -r '.download_url')
```

## Demo App
The demo app consists of:
- Frontend server (port 9000)
- Backend API (port 9001)
- Traefik reverse proxy (ports 443 and 8080)

To deploy the demo app:
```bash
git clone https://github.com/finn-rm/tafu.casa.infra.git
cd tafu.casa.infra/demo-app
docker compose up -d
```

Access the services at:
- Frontend: http://localhost/
- Backend API: http://localhost/api/health
- Traefik Dashboard: http://localhost:8080