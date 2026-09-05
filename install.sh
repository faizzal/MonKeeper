#!/usr/bin/env bash

set -e

echo "======================================"
echo " MonKeeper Installation"
echo "======================================"
echo

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not installed."
    echo "Please install Docker and Docker Compose first."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose plugin is not available."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "Creating .env..."

    POSTGRES_PASSWORD="$(openssl rand -hex 24)"
    MONKEEPER_SECRET_KEY="$(python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

    cat > .env <<ENVEOF
POSTGRES_DB=monkeeper
POSTGRES_USER=monkeeper_app
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
MONKEEPER_SECRET_KEY=${MONKEEPER_SECRET_KEY}
ENVEOF

    chmod 600 .env

    echo ".env created with generated secrets."
else
    echo ".env already exists. Keeping existing configuration."
fi

mkdir -p data/postgres

echo
echo "Building MonKeeper..."
docker compose build

echo
echo "Starting MonKeeper..."
docker compose up -d

echo
echo "Waiting for services..."
sleep 10

echo
echo "======================================"
echo " MonKeeper Status"
echo "======================================"

docker compose ps

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo
echo "======================================"
echo " Installation complete"
echo "======================================"
echo
echo "Dashboard:"
echo "http://${SERVER_IP:-SERVER-IP}"
echo
echo "API:"
echo "http://${SERVER_IP:-SERVER-IP}:8000"
echo
echo "Next step:"
echo "Open Manage Clusters and add your SolrCloud cluster."
echo
