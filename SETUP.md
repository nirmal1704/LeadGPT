# LeadGPT — Fully Free Hosted Deployment Guide

> **Last updated:** 2026-07-04  
> **Total cost: $0/month — permanently free**  
> **You need:** A browser, a credit/debit card for Oracle signup (not charged — identity verification only)

This guide deploys LeadGPT across four always-free cloud services:

| Component | Service | Cost |
|---|---|---|
| Backend API + Worker + Redis | **Oracle Cloud Free VM** | ✅ Free forever |
| Frontend (Next.js) | **Vercel** | ✅ Free forever |
| Database + Auth | **Supabase** | ✅ Free tier |
| AI inference | **Groq** | ✅ Free tier |

---

## Table of Contents

1. [Create All Accounts](#1-create-all-accounts)
2. [Supabase — Database Setup](#2-supabase--database-setup)
3. [Oracle Cloud — Create Your Free VM](#3-oracle-cloud--create-your-free-vm)
4. [Oracle Cloud — Set Up the VM](#4-oracle-cloud--set-up-the-vm)
5. [Deploy LeadGPT on the VM](#5-deploy-leadgpt-on-the-vm)
6. [Vercel — Frontend](#6-vercel--frontend)
7. [Wire Everything Together](#7-wire-everything-together)
8. [First Run Checklist](#8-first-run-checklist)
9. [Troubleshooting](#9-troubleshooting)
10. [Keeping It Running](#10-keeping-it-running)

---

## 1. Create All Accounts

Sign up for all four services before doing anything else.

### 1a. Oracle Cloud (the VM)

1. Go to [cloud.oracle.com/free](https://cloud.oracle.com/free)
2. Click **Start for free**
3. Fill in your name, country, email
4. Verify your email
5. Enter your home address and phone number
6. Add a credit or debit card — **you will not be charged**. Oracle uses it only for identity verification. Always Free resources have no charges.
7. Complete signup — takes 5–10 minutes
8. Wait for the welcome email: "Your Oracle Cloud account is ready"

> **Why a card?** Oracle requires one to prevent fake signups. Always Free resources
> never incur charges. You can set a spending limit of $0 in billing settings after signup.

### 1b. Groq (AI)

1. Go to [console.groq.com](https://console.groq.com) → sign up
2. Go to **API Keys** → **Create API Key**
3. Copy the key and save it somewhere — you'll need it later

### 1c. Supabase (database)

1. Go to [supabase.com](https://supabase.com) → **Sign Up**
2. Create a new project after signing in

### 1d. GitHub (code hosting)

1. Go to [github.com/signup](https://github.com/signup) if you don't have an account

### 1e. Vercel (frontend)

1. Go to [vercel.com](https://vercel.com) → **Sign Up with GitHub**

### 1f. GitHub Desktop (to push your code)

1. Download from [desktop.github.com](https://desktop.github.com) — this is the only thing you install locally
2. Sign in with your GitHub account

---

## 2. Supabase — Database Setup

### 2a. Create a project

1. In Supabase → **New Project**
2. Name it `leadgpt`, set a password, pick the region nearest to you
3. Wait ~2 minutes for provisioning

### 2b. Enable pgvector

1. Go to **Database → Extensions** (left sidebar)
2. Search `vector` → toggle **on**

### 2c. Run the schema

1. Go to **SQL Editor** → **New Query**
2. Open `LeadGPT/backend/db/schema.sql` on your computer in Notepad
3. Select all → Copy → Paste into the SQL editor
4. Click **Run** — you should see `Success. No rows returned.`

### 2d. Collect your credentials

Go to **Project Settings → API** and note these three values:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | Project API keys → anon/public |
| `SUPABASE_SERVICE_KEY` | Project API keys → service_role (secret) |

### 2e. Disable email confirmation (for development)

1. **Authentication → Providers → Email**
2. Toggle **Confirm email** → **off**
3. Click **Save**

### 2f. Configure auth redirect URLs

1. **Authentication → URL Configuration**
2. Under **Redirect URLs**, add: `https://your-vercel-app.vercel.app/**`
   (You'll come back and fill in the real URL after Step 6)

---

## 3. Oracle Cloud — Create Your Free VM

Oracle's Always Free tier includes 4 ARM Ampere cores and 24 GB RAM — easily enough
to run the entire LeadGPT backend stack including the Firefox browser.

### 3a. Create the VM instance

1. Log in to [cloud.oracle.com](https://cloud.oracle.com)
2. Click the hamburger menu (☰) → **Compute → Instances**
3. Click **Create Instance**
4. Fill in:
   - **Name:** `leadgpt-server`
   - **Image:** Click **Change Image** → select **Canonical Ubuntu** → **Ubuntu 22.04** → **Select Image**
   - **Shape:** Click **Change Shape** → select **Ampere** → **VM.Standard.A1.Flex**
     - Set **OCPUs:** `4`
     - Set **Memory:** `24 GB`
     - Click **Select Shape**
5. Under **Add SSH Keys:**
   - Select **Generate a key pair for me**
   - Click **Save Private Key** — this downloads a file like `ssh-key-2024-01-01.key`
   - Save this file somewhere safe on your computer (you'll need it to connect)
6. Click **Create**
7. Wait 2–3 minutes — the instance status changes to **Running**
8. Copy the **Public IP Address** shown on the instance details page

### 3b. Open firewall ports

By default Oracle blocks all traffic except SSH. You need to open ports 80 and 8000.

1. On your instance page, click the **VCN (Virtual Cloud Network)** link
2. Click **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules** and add these two rules:

**Rule 1 (for the backend API):**
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `8000`
- Description: `LeadGPT Backend API`

**Rule 2 (for future use):**
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `80`
- Description: `HTTP`

4. Click **Add Ingress Rules**

---

## 4. Oracle Cloud — Set Up the VM

You'll connect to the VM through your browser using Oracle Cloud Shell — no terminal app needed.

### 4a. Open Oracle Cloud Shell

1. In the Oracle Cloud console, click the **>_** icon in the top-right corner (Cloud Shell)
2. A terminal opens at the bottom of your browser
3. Upload your private key: click the **⋮ (three dots)** menu in Cloud Shell → **Upload** → select the `.key` file you downloaded

### 4b. Connect to your VM

In Cloud Shell, run these commands one at a time.
Replace `YOUR_VM_IP` with the public IP you copied in Step 3a.

```bash
chmod 600 ~/ssh-key-*.key
ssh -i ~/ssh-key-*.key ubuntu@YOUR_VM_IP
```

Type `yes` when asked about the host fingerprint. You're now inside your Oracle VM.

### 4c. Install Docker on the VM

Paste these commands one block at a time:

```bash
# Update the system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to the docker group (so you don't need sudo every time)
sudo usermod -aG docker ubuntu

# Apply group change immediately
newgrp docker

# Verify Docker works
docker --version
```

You should see something like `Docker version 26.x.x`.

### 4d. Open the firewall on the VM itself

Ubuntu's own firewall also needs to allow the port:

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
sudo apt-get install -y iptables-persistent
```

---

## 5. Deploy LeadGPT on the VM

Still inside the VM via Cloud Shell.

### 5a. Push your code to GitHub first

Before this step, push your `LeadGPT` folder to GitHub using GitHub Desktop:

1. Open GitHub Desktop on your computer
2. **File → Add Local Repository** → navigate to `LeadGPT/`
3. If prompted "This is not a git repository" → click **Create a Repository**
4. Click **Publish repository** → name it `leadgpt` → set **Private** → click **Publish**

### 5b. Clone your repo onto the VM

Back in your Cloud Shell SSH session:

```bash
# Install git (usually pre-installed but just in case)
sudo apt-get install -y git

# Clone your repo (replace YOUR_GITHUB_USERNAME)
git clone https://github.com/YOUR_GITHUB_USERNAME/leadgpt.git
cd leadgpt/LeadGPT
```

> If your repo is private, GitHub will ask for credentials. Use your GitHub username
> and a **Personal Access Token** (not your password).
> To create one: GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate new token → check `repo` scope → Generate.

### 5c. Create your .env file on the VM

```bash
cp .env.example .env
nano .env
```

The `nano` editor opens. Fill in every blank value:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=openai/gpt-oss-120b
GROQ_REQUESTS_PER_MINUTE=28
GROQ_TOKENS_PER_MINUTE=7500

SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

REDIS_URL=redis://redis:6379/0

NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://YOUR_VM_IP:8000

CAPSOLVER_API_KEY=
MEMORY_SIMILARITY_THRESHOLD=0.85
MAX_CONCURRENT_PAGES=2
```

When done: press **Ctrl+X** → **Y** → **Enter** to save and exit.

### 5d. Start the backend

```bash
# Build and start all services (Redis + backend API + Celery worker)
docker compose up -d --build
```

The first build takes **15–20 minutes** — it downloads Python packages, Firefox (via camoufox fetch), and the NopeCHA extension. Subsequent starts take ~20 seconds.

Watch the build:
```bash
docker compose logs -f
```

Press **Ctrl+C** to stop watching logs (services keep running).

### 5e. Verify the backend is live

```bash
curl http://localhost:8000/health
```

Expected output: `{"status":"ok"}`

You can also test from your own browser: open `http://YOUR_VM_IP:8000/health`

---

## 6. Vercel — Frontend

### 6a. Deploy

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Click **Import Git Repository** → select `leadgpt`
3. Set **Root Directory** to `frontend`
4. Before clicking Deploy, scroll to **Environment Variables** and add:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | your Supabase Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | your Supabase anon key |
| `NEXT_PUBLIC_API_URL` | `http://YOUR_ORACLE_VM_IP:8000` |

5. Click **Deploy** — takes 2–3 minutes
6. Copy your Vercel URL: `https://leadgpt-xxxx.vercel.app`

### 6b. Update Supabase with your Vercel URL

1. Supabase → **Authentication → URL Configuration**
2. **Site URL:** `https://leadgpt-xxxx.vercel.app`
3. **Redirect URLs:** `https://leadgpt-xxxx.vercel.app/**`
4. Click **Save**

---

## 7. Wire Everything Together

### Summary of all values you should have by now:

| Value | Where you got it |
|---|---|
| Oracle VM Public IP | Step 3a |
| Supabase URL | Step 2d |
| Supabase Anon Key | Step 2d |
| Supabase Service Key | Step 2d |
| Groq API Key | Step 1b |
| Vercel URL | Step 6a |

### Double-check your `.env` on the VM

```bash
# On the VM — view your .env
cat ~/leadgpt/LeadGPT/.env
```

Confirm:
- `NEXT_PUBLIC_API_URL=http://YOUR_VM_IP:8000` — matches your actual VM IP
- All Supabase values are filled in
- `GROQ_API_KEY` starts with `gsk_`
- `REDIS_URL=redis://redis:6379/0` — exactly this, no changes needed

If you change anything in `.env`, restart the services:

```bash
cd ~/leadgpt/LeadGPT
docker compose down && docker compose up -d
```

---

## 8. First Run Checklist

```
[ ] 1. Oracle VM is in "Running" state
[ ] 2. VM firewall (Security List) has port 8000 open
[ ] 3. Ubuntu iptables has port 8000 open
[ ] 4. docker compose up -d ran successfully on the VM
[ ] 5. curl http://YOUR_VM_IP:8000/health returns {"status":"ok"}
[ ] 6. Supabase schema.sql has been run — all 9 tables visible in Table Editor
[ ] 7. Supabase pgvector extension is enabled
[ ] 8. Supabase email confirmation is OFF
[ ] 9. Vercel deployment succeeded — no build errors
[ ] 10. Vercel has all 3 NEXT_PUBLIC_* environment variables

[ ] 11. Open https://your-vercel-url.vercel.app — app loads
[ ] 12. Sign up with email + password
[ ] 13. Go to Projects → Create a project (e.g. "Test Campaign")
[ ] 14. Back in chat — describe your leads:
         "I'm a web designer in Delhi looking for 10 restaurants without a website"
[ ] 15. Intake agent replies (may ask a follow-up or confirm directly)
[ ] 16. Job starts — progress shows "Planning search strategy"
[ ] 17. After completion — "Download Excel" button appears and downloads a .xlsx file ✅
```

---

## 9. Troubleshooting

### "Connection refused" when opening the app backend URL

Check the services are running on the VM:
```bash
docker compose ps
```
All three services (`redis`, `backend`, `worker`) should show `Up`.

If any are down:
```bash
docker compose logs backend
docker compose logs worker
```

### Job stuck in "queued" forever

The worker isn't processing. Check:
```bash
docker compose logs worker
```
Look for `celery@... ready` — if you see an error instead, it's usually a missing `.env` value.

### Frontend loads but can't connect to the backend

- Check `NEXT_PUBLIC_API_URL` in Vercel is `http://YOUR_ACTUAL_VM_IP:8000`
- In your browser's developer tools (F12 → Network tab), look for a failed request to see the exact URL being called
- Make sure port 8000 is open in both the Oracle Security List AND the VM's iptables rules

### "Invalid token" / 401 errors after logging in

- Confirm `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Vercel matches the anon key in Supabase
- Confirm the Supabase Site URL is set to your Vercel URL (not localhost)

### Docker build fails with "no space left"

The VM has limited disk space:
```bash
docker system prune -a   # removes unused images and containers
docker compose up -d --build
```

### VM became unreachable

Oracle VMs occasionally need a soft reboot:
1. Oracle Cloud console → **Compute → Instances → leadgpt-server**
2. Click **Actions → Reboot**
3. Wait 2 minutes → reconnect via Cloud Shell

After reboot, services should restart automatically (`restart: unless-stopped` in docker-compose.yml).
If they don't:
```bash
ssh -i ~/ssh-key-*.key ubuntu@YOUR_VM_IP
cd leadgpt/LeadGPT
docker compose up -d
```

---

## 10. Keeping It Running

### The VM runs 24/7 for free

Oracle's Always Free ARM VMs never stop. Your LeadGPT backend stays online permanently.

### Auto-restart on reboot

The `restart: unless-stopped` setting in `docker-compose.yml` means Docker services
automatically restart if the VM reboots. You don't need to do anything.

### Deploying code updates

When you update your code:

1. On your computer: make changes → commit in GitHub Desktop → Push
2. On the VM (via Cloud Shell):

```bash
ssh -i ~/ssh-key-*.key ubuntu@YOUR_VM_IP
cd ~/leadgpt/LeadGPT
git pull
docker compose up -d --build
```

Vercel redeploys the frontend automatically whenever you push to GitHub.

### Monitoring

View live logs from any service:
```bash
docker compose logs -f backend    # FastAPI logs
docker compose logs -f worker     # Celery + job logs
docker compose logs -f redis      # Redis logs
```

---

## Cost Summary

| Service | Always Free? | Limits |
|---|---|---|
| Oracle Cloud VM | ✅ Yes | 4 ARM cores, 24GB RAM, 200GB storage |
| Vercel | ✅ Yes | 100GB bandwidth/month |
| Supabase | ✅ Yes | 500MB database, 50,000 MAU |
| Groq | ✅ Free tier | 7,500 tokens/min, 28 req/min |
| **Total** | **$0/month** | |

Oracle Cloud explicitly guarantees Always Free resources will never expire and will
never be charged. See [oracle.com/cloud/free](https://www.oracle.com/cloud/free/).
