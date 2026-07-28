# Alternative: Oracle Cloud "Always Free" (no 12-month expiry)

AWS's free tier works fine and is well-documented (see
`aws-ec2-deploy.md`), but it's worth knowing the honest tradeoff: AWS gives
you a `t2.micro`/`t3.micro` (1 vCPU, 1 GB RAM) free for 12 months, then it
starts billing. **Oracle Cloud Infrastructure (OCI)'s Always Free tier has
no expiry date** and gives meaningfully more compute:

| | AWS Free Tier | OCI Always Free |
|---|---|---|
| Compute | 1 vCPU / 1 GB RAM | up to 4 ARM OCPUs / 24 GB RAM (splittable across VMs) |
| Time limit | 12 months, then billed | none — free indefinitely |
| Storage | 30 GB EBS | 200 GB block storage |
| Egress | ~100 GB/month | 10 TB/month |
| Credit card | required | required for verification, not charged for always-free usage |

The catch: OCI's free ARM capacity is sometimes hard to provision in
popular regions (retry if you hit "out of capacity"), and Oracle can
reclaim an Always Free instance that sits essentially idle for an extended
period — not a concern once your demo has real traffic, but don't let it
sit completely untouched for weeks.

**Everything else in this repo works unchanged** — `docker-compose.yml`,
`scripts/deploy_ec2.sh`, and the GitHub Actions workflow all just need an
SSH-reachable Ubuntu box; they don't care which cloud it's on.

## Steps

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com) (free, card
   required for identity verification only).
2. Create an instance: **Compute → Instances → Create Instance**.
   - Image: **Canonical Ubuntu 22.04** (Always Free eligible)
   - Shape: **VM.Standard.A1.Flex** (ARM, Always Free) — 2-4 OCPUs, 12-24 GB
     RAM, whatever you leave for other free VMs
   - Networking: create/attach a VCN with a public IP, and in the subnet's
     **Security List**, add ingress rules for TCP 22 and TCP 80 (0.0.0.0/0)
   - Add your SSH public key during creation
3. Once running, note the public IP, then reuse the exact same deploy flow
   as AWS:

```bash
export OPENAI_API_KEY=sk-proj-...
./scripts/deploy_ec2.sh <oci-public-ip> <path-to-private-key> ubuntu
```

4. Because the shape is ARM64, double-check `docker compose up -d --build`
   pulls ARM-compatible base images — `python:3.12-slim`, `node:20-slim`,
   and `nginx:1.27-alpine` (already used in this repo's Dockerfiles) all
   publish multi-arch manifests, so no changes needed.
5. Store your OpenAI key the same way (`.env` on the box, chmod 600) or via
   OCI Vault if you want a managed-secrets equivalent to AWS SSM.

## Other free options worth knowing about

- **Google Cloud**: a permanent free `e2-micro` (0.25 vCPU / 1 GB RAM) —
  smaller than OCI's, but genuinely free forever, no card charge risk.
- **Fly.io / Render**: easiest Docker-native deploys, generous free
  allowances, but free-tier services on Render sleep after inactivity and
  don't guarantee persistent disk — fine for stateless demos, less ideal
  for this app's SQLite file unless you attach a paid volume.
- **Cloudflare / Vercel**: great for the frontend as a static build, but
  you'd still need one of the above for the FastAPI backend + SQLite.

**Recommendation for your case**: AWS free tier is perfectly fine to start
with since you already have the guide — but if you want the demo to keep
running past 12 months without needing to migrate or pay, Oracle's Always
Free tier is the stronger long-term choice for exactly this workload.
