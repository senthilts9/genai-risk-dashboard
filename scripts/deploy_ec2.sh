#!/usr/bin/env bash
# Deploys this project to an EC2 instance you've already launched
# (see deploy/aws-ec2-deploy.md for how to launch + open the security group).
#
# Usage:
#   export OPENAI_API_KEY=sk-proj-...
#   ./scripts/deploy_ec2.sh <ec2-public-ip> <path-to-ssh-key.pem> [ssh-user]
#
# What it does:
#   1. rsyncs the project to the instance (excludes node_modules, .git, etc.)
#   2. installs Docker on the instance if it's missing
#   3. writes OPENAI_API_KEY into a chmod-600 .env file on the instance
#      (docker compose reads .env automatically; the key never touches git)
#   4. runs `docker compose up -d --build`
#
set -euo pipefail

HOST="${1:?Usage: ./scripts/deploy_ec2.sh <ec2-public-ip> <key.pem> [user]}"
KEY="${2:?Usage: ./scripts/deploy_ec2.sh <ec2-public-ip> <key.pem> [user]}"
USER="${3:-ubuntu}"
REMOTE_DIR="~/genai-risk-dashboard"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: export OPENAI_API_KEY before running this script." >&2
  exit 1
fi

SSH_OPTS="-i $KEY -o StrictHostKeyChecking=accept-new"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Syncing project files to $USER@$HOST:$REMOTE_DIR"
ssh $SSH_OPTS "$USER@$HOST" "mkdir -p $REMOTE_DIR"
rsync -az --delete \
  --exclude '.git' --exclude 'node_modules' --exclude '__pycache__' \
  --exclude 'dist' --exclude 'backend/risk.db' --exclude 'backend/data' \
  -e "ssh $SSH_OPTS" \
  "$PROJECT_DIR"/ "$USER@$HOST:$REMOTE_DIR/"

echo "==> Ensuring Docker is installed on the instance"
ssh $SSH_OPTS "$USER@$HOST" '
  if ! command -v docker >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo usermod -aG docker $USER
  fi
'

echo "==> Writing .env with your OpenAI key (chmod 600, not committed to git)"
ssh $SSH_OPTS "$USER@$HOST" "cat > $REMOTE_DIR/.env << EOF
OPENAI_API_KEY=$OPENAI_API_KEY
EOF
chmod 600 $REMOTE_DIR/.env"

echo "==> Building and starting containers"
ssh $SSH_OPTS "$USER@$HOST" "cd $REMOTE_DIR && sudo docker compose up -d --build"

echo "==> Done. Visit: http://$HOST"
