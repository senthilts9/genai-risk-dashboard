#!/usr/bin/env bash
# Pushes this project to a GitHub repo you create.
#
# Usage:
#   1. Create an empty repo on GitHub (no README/license, so it's truly empty):
#        https://github.com/new
#   2. Run:  ./scripts/push_to_github.sh git@github.com:<you>/<repo>.git
#      (or the https:// URL if you use a personal access token instead of SSH)
#
set -euo pipefail

REMOTE_URL="${1:?Usage: ./scripts/push_to_github.sh <git-remote-url>}"

cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  git init
  git branch -M main
fi

cat > .gitignore << 'EOF'
__pycache__/
*.pyc
node_modules/
dist/
backend/risk.db
backend/data/
.env
.DS_Store
EOF

git add -A
git commit -m "GenAI application risk dashboard: FastAPI + React, OpenAI-backed, AWS free-tier deploy" || echo "Nothing new to commit"

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

git push -u origin main

echo "Pushed. Repo: $REMOTE_URL"
