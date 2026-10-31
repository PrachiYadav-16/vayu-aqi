#!/usr/bin/env bash
# One-command install of Vayu on a fresh Ubuntu VM (Oracle Cloud Always Free).
#
#   curl -fsSL https://raw.githubusercontent.com/PrachiYadav-16/vayu-aqi/main/deploy/oracle/setup.sh | bash
#
# Optional environment variables:
#   VAYU_REPO    git URL to clone (default: the public GitHub repo)
#   VAYU_DOMAIN  your own domain; default is <public-ip>.sslip.io, which needs no DNS setup
#   VAYU_DIR     install folder (default: ~/vayu-aqi)
set -euo pipefail

REPO="${VAYU_REPO:-https://github.com/PrachiYadav-16/vayu-aqi.git}"
DIR="${VAYU_DIR:-$HOME/vayu-aqi}"

say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }

say "Installing Docker"
sudo apt-get update -y >/dev/null
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker

say "Opening ports 80 and 443 in the VM firewall"
# Oracle's Ubuntu images ship iptables rules that reject everything except SSH.
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 1 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  fi
done
if ! command -v netfilter-persistent >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent >/dev/null
fi
sudo netfilter-persistent save >/dev/null

say "Getting the code"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  sudo apt-get install -y git >/dev/null
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

say "Working out the address"
IP="$(curl -fsS https://api.ipify.org || curl -fsS https://ifconfig.me)"
DOMAIN="${VAYU_DOMAIN:-$(echo "$IP" | tr . -).sslip.io}"
echo "Public IP: $IP"
echo "Address:   https://$DOMAIN"

say "Writing configuration"
mkdir -p secrets
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  SECRET="$(openssl rand -hex 32)"
  sed -i "s|^VAYU_JWT_SECRET=.*|VAYU_JWT_SECRET=$SECRET|" backend/.env
  sed -i "s|^VAYU_CORS_ORIGINS=.*|VAYU_CORS_ORIGINS=https://$DOMAIN|" backend/.env
  echo "Created backend/.env with a new random JWT secret."
else
  echo "Keeping existing backend/.env"
fi
if [ ! -f deploy/oracle/.env ]; then
  printf 'VAYU_DOMAIN=%s\nVAYU_SEED_DEMO=true\n' "$DOMAIN" > deploy/oracle/.env
fi

say "Building and starting (first build takes 5 to 10 minutes)"
cd deploy/oracle
sudo docker compose up -d --build

say "Waiting for the app to answer"
for _ in $(seq 1 60); do
  if sudo docker compose exec -T app python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

cat <<EOF

Vayu is running.

  Open:          https://$DOMAIN
  Demo login:    demo@vayu.local / vayu-demo-2026
  Logs:          cd $DIR/deploy/oracle && sudo docker compose logs -f app
  Update later:  bash $DIR/deploy/oracle/update.sh

If the page does not open, check that ports 80 and 443 are allowed in the
Oracle console (Networking > Virtual cloud networks > your VCN > Security
Lists > Default > Add Ingress Rules). The HTTPS certificate is issued on the
first visit and can take a minute.
EOF
