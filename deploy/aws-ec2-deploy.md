# Deploying to AWS Free Tier (EC2)

This deploys both containers (FastAPI backend + React/nginx frontend) on a
single free-tier EC2 instance via docker-compose. It's the simplest path that
stays inside the free tier and matches the code in this repo exactly.

## 1. Launch the instance

- AMI: Ubuntu Server 22.04 LTS (or Amazon Linux 2023)
- Instance type: `t2.micro` or `t3.micro` — both are free-tier eligible
  (750 hrs/month for the first 12 months on a new account)
- Storage: 20–30 GB gp3 (free tier includes 30 GB EBS)
- Security group inbound rules:
  - TCP 22 (SSH) — restrict to your IP
  - TCP 80 (HTTP) — 0.0.0.0/0
- Create/attach a key pair for SSH access

## 2. Store the API key securely (don't put it in a file on disk)

```bash
aws ssm put-parameter \
  --name "/genai-risk-dashboard/openai-api-key" \
  --value "sk-proj-..." \
  --type SecureString
```

Your EC2 instance profile/IAM role needs `ssm:GetParameter` on this
parameter path. This avoids ever writing the key to `.env` on the box.

## 3. Install Docker on the instance

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin awscli
sudo usermod -aG docker $USER
newgrp docker
```

## 4. Get the code onto the instance

Copy the `genai-risk-dashboard/` folder up (scp, git clone from your own
repo, or `aws s3 cp` if you've zipped and uploaded it to S3):

```bash
scp -i your-key.pem -r genai-risk-dashboard ubuntu@<EC2_PUBLIC_IP>:~/
```

## 5. Fetch the key and launch

```bash
cd ~/genai-risk-dashboard
export OPENAI_API_KEY=$(aws ssm get-parameter \
  --name "/genai-risk-dashboard/openai-api-key" \
  --with-decryption --query "Parameter.Value" --output text)

docker compose up -d --build
```

Visit `http://<EC2_PUBLIC_IP>` — the dashboard is live. The SQLite risk
database persists in the `risk-data` docker volume across restarts.

## 6. (Optional) Make it durable / production-ish

- Allocate an **Elastic IP** so the address survives instance stop/start
  (free while attached to a running instance).
- Put a **Route 53** hosted zone + domain in front, and terminate TLS with
  an **ACM** certificate on an **Application Load Balancer** — ALB is not
  in the always-free tier, so for a pure free-tier demo skip this and use
  the plain EC2 public IP over HTTP, or terminate TLS with Caddy/nginx +
  Let's Encrypt directly on the instance instead of an ALB.
- Add a `systemd` unit or a `cron @reboot` line running
  `docker compose up -d` so the stack survives an instance reboot.

## Running a small public demo safely (e.g. a $25 budget)

If you're sharing the URL with recruiters/friends on LinkedIn rather than
running this privately:

1. **Set a hard OpenAI spend cap below your budget** — platform.openai.com →
   Billing → Limits → set it to ~$20 (leaves headroom so a cap trip doesn't
   also break in-flight requests at exactly $25).
2. **The app already rate-limits itself.** `DAILY_INVOKE_LIMIT` and
   `DAILY_COPILOT_LIMIT` (both default to 60/day) cap total OpenAI-backed
   requests per day across *all* visitors combined, regardless of who's
   asking — past the limit, users get a friendly "demo budget reached,
   check back tomorrow" message instead of the app silently burning
   through your card. Tune them via environment variables in
   `docker-compose.yml` if 60/day feels too generous or too tight.
3. **Default model is `gpt-4o-mini`** (cheapest OpenAI model) for both the
   live invoke console and the Risk Copilot, so 60 calls/day costs cents,
   not dollars.
4. **The Quant Lab tabs cost nothing** — `yfinance` market data is free, so
   recruiters can explore Portfolio/Volatility/Derivatives/Fixed Income
   freely without touching your OpenAI budget at all.

## 7. Scaling beyond the free-tier demo

If this grows past a single instance, the natural next step is:
`ECS Fargate` (backend) + `S3 + CloudFront` (static frontend) +
`DynamoDB` (replace SQLite — swap only `backend/app/storage.py`) +
`Secrets Manager` for the API key. That's outside free-tier scope but the
application code doesn't need to change, only `storage.py`.
