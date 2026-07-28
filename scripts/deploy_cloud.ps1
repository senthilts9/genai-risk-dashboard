#!/usr/bin/env pwsh
# deploy_cloud.ps1 — Deploy Meridian to any SSH-accessible cloud server (AWS EC2 or Oracle OCI)
#
# Usage:
#   .\scripts\deploy_cloud.ps1 -ServerIP "116.86.75.194" -KeyFile "$env:USERPROFILE\.ssh\meridian_deploy" -OpenAIKey "sk-proj-..."
#
# The script:
#   1. SSH into the server
#   2. Installs Docker if not present
#   3. Clones / updates the repo from GitHub
#   4. Writes the .env file (600 perms — not committed to git)
#   5. Runs docker compose up --build -d
#   6. Prints the live URL

param(
    [Parameter(Mandatory)][string]$ServerIP,
    [string]$User       = "ubuntu",
    [string]$KeyFile    = "$env:USERPROFILE\.ssh\meridian_deploy",
    [Parameter(Mandatory)][string]$OpenAIKey,
    [int]$DailyLimit    = 60
)

$ErrorActionPreference = "Stop"
$repo = "https://github.com/senthilts9/genai-risk-dashboard.git"
$appDir = "~/genai-risk-dashboard"

function Ssh-Run([string]$cmd) {
    Write-Host "> $cmd" -ForegroundColor Cyan
    ssh -i $KeyFile -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "${User}@${ServerIP}" $cmd
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed: $cmd" }
}

Write-Host "`n=== Meridian Cloud Deploy ===" -ForegroundColor Green
Write-Host "Target : $User@$ServerIP"
Write-Host "Key    : $KeyFile"
Write-Host "Repo   : $repo"

# 1. Test connectivity
Write-Host "`n[1/6] Testing SSH connectivity..." -ForegroundColor Yellow
Ssh-Run "echo 'SSH OK'"

# 2. Install Docker + git if missing
Write-Host "`n[2/6] Installing Docker & git..." -ForegroundColor Yellow
Ssh-Run "sudo apt-get update -qq && sudo apt-get install -y -qq docker.io docker-compose-plugin git curl"
Ssh-Run "sudo usermod -aG docker \$USER || true"

# 3. Clone or pull repo
Write-Host "`n[3/6] Cloning / updating repo..." -ForegroundColor Yellow
Ssh-Run "if [ -d $appDir ]; then cd $appDir && git pull; else git clone $repo $appDir; fi"

# 4. Write .env
Write-Host "`n[4/6] Writing .env (key never logged)..." -ForegroundColor Yellow
$envContent = @"
OPENAI_API_KEY=$OpenAIKey
DAILY_INVOKE_LIMIT=$DailyLimit
DAILY_COPILOT_LIMIT=$DailyLimit
RISK_WINDOW_SIZE=50
CORS_ORIGINS=*
"@
# Write via heredoc over SSH so the key never touches a remote shell arg
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($envContent))
Ssh-Run "echo '$b64' | base64 -d > $appDir/.env && chmod 600 $appDir/.env"

# 5. Launch with Docker Compose
Write-Host "`n[5/6] Building & starting containers..." -ForegroundColor Yellow
Ssh-Run "cd $appDir && sudo docker compose up -d --build 2>&1 | tail -20"

# 6. Health check
Write-Host "`n[6/6] Health check..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Ssh-Run "curl -sf http://localhost:8000/api/health && echo ' Backend OK' || echo ' Backend not yet ready (try again in 30s)'"

Write-Host "`n=== DEPLOYMENT COMPLETE ===" -ForegroundColor Green
Write-Host "App is live at: http://$ServerIP" -ForegroundColor Green
Write-Host "API health  : http://$ServerIP/api/health"
Write-Host "`nTo view logs: ssh -i $KeyFile ${User}@${ServerIP} 'cd ~/genai-risk-dashboard && docker compose logs -f'"
