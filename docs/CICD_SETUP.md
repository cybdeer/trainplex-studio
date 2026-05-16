# TrainPlex Studio - CI/CD Setup

This document captures the CI/CD pipeline created in Phase 1 Step 10 and the
one-time manual setup that must happen in the GitHub UI and on the staging /
production servers before the workflows can run end-to-end.

---

## 1. Files created / updated

| Path | Purpose |
| --- | --- |
| `.github/workflows/test.yml` | Lint + unit tests + Docker build verification. Runs on every PR and on pushes to `develop` / `main`. Five parallel jobs: `lint-backend`, `lint-frontend`, `test-backend`, `test-frontend`, `build-docker`. Concurrency-cancels stale runs on the same PR. |
| `.github/workflows/deploy-staging.yml` | Build + push image to `ghcr.io/<owner>/trainplex-studio:staging-<sha>` and `:staging-latest`, SSH to the staging server, `docker compose pull && up -d`, run `/health` smoke test, ping WhatsApp webhook on failure. Triggered on push to `develop`. |
| `.github/workflows/deploy-prod.yml` | Three-stage prod pipeline: (1) backup DB via SSH, gated by `production` environment approval, (2) build + push `prod-<sha>` image to GHCR, (3) SSH deploy with migrations, 60s health check window, auto-rollback to previous image on failure, WhatsApp notification on success or failure. Triggered on push to `main`. |
| `.github/dependabot.yml` | Weekly Monday 09:00 London dependency updates for GitHub Actions, pip (Python via `pyproject.toml`), and npm (`web/yarn.lock`). Minor + patch updates are grouped into a single PR per ecosystem. |
| `.github/CODEOWNERS` | Solo-dev phase: `@ilo265` owns everything. Pattern in place so it is trivial to split by area as the team grows. |
| `.github/pull_request_template.md` | Checkbox-driven PR template covering tests, plan reference, UI screenshots, breaking change flag, and the no-founder-personal-number rule. |

---

## 2. Secrets to add (GitHub Settings -> Secrets and variables -> Actions)

All listed under **Repository secrets** unless marked otherwise.

### Required for staging (`deploy-staging.yml`)

| Secret | Description |
| --- | --- |
| `STAGING_SSH_KEY` | Private SSH key (PEM, no passphrase) for the deploy user on the staging server. |
| `STAGING_HOST` | Hostname or IP of the staging server, e.g. `staging.trainplex.studio` or `10.0.1.42`. |
| `STAGING_USER` | *(optional, defaults to `deploy`)* SSH user. |
| `STAGING_SSH_PORT` | *(optional, defaults to `22`)* SSH port. |

### Required for production (`deploy-prod.yml`)

| Secret | Description |
| --- | --- |
| `PROD_SSH_KEY` | Private SSH key (PEM, no passphrase) for the deploy user on the prod server. **Separate key from staging.** |
| `PROD_HOST` | Hostname or IP of the production server. |
| `PROD_USER` | *(optional, defaults to `deploy`)* SSH user. |
| `PROD_SSH_PORT` | *(optional, defaults to `22`)* SSH port. |

### Shared

| Secret | Description |
| --- | --- |
| `WA_NOTIFY_WEBHOOK` | Webhook URL that accepts `POST {"text": "..."}` and forwards to the ops WhatsApp group via **official channels only**. **Per house rule: never use the founder's personal mobile in this webhook target.** |
| `GITHUB_TOKEN` | Auto-provisioned by GitHub. Already has `packages: write` granted via the `permissions:` block; no manual setup needed. |
| `CODECOV_TOKEN` | *(optional)* Only needed if you re-enable the upstream coverage upload steps. The new workflows do not require it. |

### Repository **variables** (optional - not secret)

Variables, not secrets. Settings -> Secrets and variables -> Actions -> **Variables** tab.

| Variable | Default | Description |
| --- | --- | --- |
| `STAGING_URL` | `https://staging.trainplex.studio` | Base URL used by the staging smoke test. |
| `PROD_URL` | `https://app.trainplex.studio` | Base URL used by the prod health check and shown as the environment link in the GitHub UI. |

---

## 3. Branch protection rules (GitHub UI)

Settings -> Branches -> Add branch protection rule.

### Rule: `develop`

- Require a pull request before merging
  - Required approving reviews: **1**
  - Dismiss stale approvals on new commits: **on**
  - Require review from Code Owners: **on**
- Require status checks to pass before merging
  - Require branches to be up to date: **on**
  - Required checks (from `test.yml`):
    - `Lint Backend (black + ruff)`
    - `Lint Frontend (eslint + prettier)`
    - `Test Backend (pytest SQLite)`
    - `Test Frontend (yarn unit)`
    - `Build Docker Image (verify Dockerfile)`
- Require conversation resolution before merging: **on**
- Require linear history: **on** (recommended)
- Restrict who can push: **on**, allow only @ilo265 and `github-actions[bot]`
- Do **not** allow force pushes or deletions

### Rule: `main`

Same as `develop`, plus:

- Required approving reviews: **1** (will be self-approve until the team grows; the production environment also enforces a manual approval gate so this is not the only safety net)
- Lock branch: leave **off** (we need to merge into it)
- Require deployments to succeed before merging: **off** (we deploy *after* merge, not before)

---

## 4. GitHub Environment setup (required for prod approval gate)

Settings -> Environments -> **New environment**.

### Environment: `production`

- **Required reviewers**: add `@ilo265` (and any future approvers). The `deploy-prod.yml` workflow blocks at the `approval-and-backup` job until a reviewer clicks Approve in the Actions UI.
- **Wait timer**: 0 minutes (manual approval is the gate).
- **Deployment branches**: restrict to `main` only.
- **Environment URL**: `https://app.trainplex.studio` (or your prod URL) - shown next to the green deploy badge.
- **Environment secrets** (optional): if you want to keep `PROD_SSH_KEY` etc. scoped to this environment instead of the whole repo, move them here. Recommended once a second engineer joins.

No environment is needed for staging; the workflow runs unattended.

---

## 5. Manual server setup

These steps run **once per server** (staging and prod). The workflows assume the following already exists.

### 5.1 Provision the server

- Ubuntu 22.04 LTS (or any distro with Docker + Docker Compose v2).
- Open inbound TCP 22 (SSH, restrict to GitHub Actions IP ranges or use a bastion), 80, 443.
- Create a dedicated non-root deploy user, e.g.:
  ```bash
  sudo adduser --disabled-password --gecos "" deploy
  sudo usermod -aG docker deploy
  sudo mkdir -p /home/deploy/.ssh && sudo chown deploy:deploy /home/deploy/.ssh
  ```

### 5.2 Authorise the GitHub Actions SSH key

- Generate a fresh keypair locally for each environment (do **not** reuse personal keys):
  ```bash
  ssh-keygen -t ed25519 -f trainplex-staging -N ""
  ssh-keygen -t ed25519 -f trainplex-prod    -N ""
  ```
- Copy each **public** key into the deploy user's `~/.ssh/authorized_keys` on the matching server.
- Paste each **private** key into the corresponding GitHub secret (`STAGING_SSH_KEY`, `PROD_SSH_KEY`).
- Delete the local private key copies once stored.

### 5.3 Install Docker + Compose v2

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo apt-get install -y docker-compose-plugin
docker --version && docker compose version
```

### 5.4 Lay out the deploy directory

Both workflows `cd /opt/trainplex-studio` on the remote host. Create it with:

```bash
sudo mkdir -p /opt/trainplex-studio
sudo chown deploy:deploy /opt/trainplex-studio
cd /opt/trainplex-studio
```

Then drop in a `docker-compose.yml` (or symlink from this repo) that references the image via the `TRAINPLEX_IMAGE` env var, e.g.:

```yaml
services:
  app:
    image: ${TRAINPLEX_IMAGE:-ghcr.io/<owner>/trainplex-studio:staging-latest}
    restart: unless-stopped
    env_file: .env
    ports:
      - "8080:8080"
```

Also create an `.env` file with DB credentials, `LABEL_STUDIO_HOST`, secret key, etc. The workflows never touch `.env`.

### 5.5 Production-only: DB backup script

`deploy-prod.yml` calls `/opt/trainplex-studio/scripts/backup-db.sh <backup_id>` over SSH **before** the new image rolls out. Stub example:

```bash
#!/usr/bin/env bash
set -euo pipefail
BACKUP_ID="${1:?backup id required}"
DEST="/var/backups/trainplex/${BACKUP_ID}.sql.gz"
mkdir -p "$(dirname "$DEST")"
# Assumes Postgres in a docker compose service named "db".
docker compose -f /opt/trainplex-studio/docker-compose.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DEST"
echo "Backup written: $DEST"
```

Make it executable: `chmod +x /opt/trainplex-studio/scripts/backup-db.sh`.

Also rotate or off-site the backups (cron + S3 / Backblaze etc.) - the workflow does not retain them itself.

### 5.6 Health endpoint

Both smoke tests `curl` `${STAGING_URL}/health` / `${PROD_URL}/health` and expect HTTP 200. Confirm Label Studio's existing health probe responds at `/health`, or add a tiny reverse-proxy alias if it lives elsewhere. If the endpoint changes, update the `STAGING_URL` / `PROD_URL` variables and the curl path inside each workflow.

### 5.7 WhatsApp webhook target

The `WA_NOTIFY_WEBHOOK` URL must be a server we control (or a no-code bridge like Twilio / Whapi / 2chat) that pushes the JSON payload to the **official ops WhatsApp number**. Per house rule, the founder's personal `<configured-guard>` mobile must never appear as the target - use an official business number.

---

## 6. First-run checklist

In order:

1. Push the workflow files to `develop` via a PR. The `test.yml` checks run on the PR itself.
2. Merge the PR. `deploy-staging.yml` fires and exposes any server-side gaps.
3. Add the secrets and variables from section 2.
4. Configure the `production` environment from section 4.
5. Configure the branch protection rules from section 3.
6. Create a second PR from `develop` to `main`. After merge, `deploy-prod.yml` runs and blocks on approval - approve it manually to validate the gate.
7. Confirm a WhatsApp notification lands on the ops number for both a success and a forced-failure run.

---

## 7. Notes / follow-ups

- The upstream Label Studio repo ships ~50 workflow files under `.github/workflows/`. The three TrainPlex-specific workflows added here are additive; they do not delete or disable the upstream pipelines, so they will all queue together on push. If they ever conflict (job-name collisions, rate limits, etc.) you can prune the upstream workflows that are no longer relevant to TrainPlex.
- `test.yml` runs frontend lint via `yarn lint`, which today maps to `biome check --write .`. If you swap biome out for raw `eslint` + `prettier`, the same script name keeps working - no workflow edit needed.
- `test.yml` runs `yarn test:unit --watchAll=false` first and falls back to `yarn test --watchAll=false` so the workflow works regardless of which test script name lands in `package.json`.
- The auto-rollback path in `deploy-prod.yml` records the previously running image to `/opt/trainplex-studio/.previous_image` on the remote host **inside the same SSH session that pulls the new image**. If you ever swap the deploy script to a blue-green pattern, drop that step in favour of an explicit traffic switch.
- Every production fix that flows through this pipeline must still be appended to `/var/lib/trainplex-data/INCIDENT_LOG.md` per the house incident-log rule.
