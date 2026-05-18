# 📖 Detailed Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Google Chrome | Latest | For LinkedIn scraping |
| Git | Any | For GitHub push |
| Gmail account | — | For approval emails |

---

## Step 1 — Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/job-agent.git
cd job-agent
chmod +x scripts/setup.sh
./scripts/setup.sh
```

---

## Step 2 — Get Your Credentials

### 🔑 Anthropic API Key (Claude AI)
1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an account / log in
3. **API Keys** → **Create Key**
4. Copy it into `.env` as `ANTHROPIC_API_KEY`

### 🔑 LinkedIn Session Cookie (LI_AT)
1. Open Chrome, log into [linkedin.com](https://linkedin.com)
2. Press `F12` → **Application** tab → **Cookies** → `https://www.linkedin.com`
3. Find the cookie named `li_at`
4. Copy its **Value** into `.env` as `LI_AT`

> ⚠️ This cookie expires every ~30 days. Re-copy it when scraping stops working.

### 🔑 Gmail App Password (for SMTP emails)
1. Go to [myaccount.google.com](https://myaccount.google.com)
2. **Security** → **2-Step Verification** (must be enabled)
3. Scroll to bottom → **App passwords**
4. Generate one for "Mail / Other (Custom name: Job Agent)"
5. Copy the 16-char password into `.env` as `SMTP_PASSWORD`

---

## Step 3 — Configure .env

```bash
nano .env   # or open in VS Code
```

Fill in all values from `.env.example`.

---

## Step 4 — Add Your Resume

Place your Word resume at:
```
data/resumes/base_resume.docx
```

Tips:
- Use a clean, well-structured resume
- Use standard section headings: **Summary**, **Skills**, **Experience**
- The AI will only modify Summary, Skills, and bullet points

---

## Step 5 — (Optional) Run the Approval Server

For the approve/skip email links to work, you need a running server.

**Option A — Local with ngrok (recommended for testing):**
```bash
# Terminal 1: start the server
python agents/approval_server.py

# Terminal 2: expose it publicly
ngrok http 8080
# Copy the https://xxxxx.ngrok.io URL into .env as APPROVAL_BASE_URL
```

**Option B — Run without server (simpler):**
Skip the approval server. The email will still arrive, but you'll need to manually edit `data/jobs/found_jobs.json` and set `"status": "approved"` for jobs you want to apply to. Then run:
```bash
python agents/orchestrator.py --apply-only
```

---

## Step 6 — Run the Agent

```bash
# Full pipeline
python agents/orchestrator.py

# Or use the shortcut
./scripts/run_agent.sh

# Only search & email (no applying)
python agents/orchestrator.py --search-only

# Only apply to already-approved jobs
python agents/orchestrator.py --apply-only
```

---

## Step 7 — Push to GitHub

```bash
# Initialize git (if not already)
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/job-agent.git

# Add all files (gitignore protects .env and personal data)
git add .
git commit -m "feat: initial job agent setup"
git push -u origin main
```

---

## Step 8 — Add GitHub Secrets (for Actions automation)

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `LI_AT` | Your LinkedIn session cookie |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail App Password |
| `APPROVAL_BASE_URL` | Your approval server URL (optional) |

After adding secrets, the agent will run automatically every day at 8 AM UAE time.

---

## Troubleshooting

**LinkedIn scraping returns no jobs:**
- Check your `LI_AT` cookie — it may have expired
- Try reducing `max_jobs_per_run` in `config/settings.yaml`
- Check `data/logs/agent.log` for errors

**Email not sending:**
- Verify `SMTP_USER` and `SMTP_PASSWORD` are correct
- Make sure you're using an App Password, not your real Gmail password
- Check that 2-Step Verification is enabled on your Google account

**Resume not being tailored:**
- Ensure `data/resumes/base_resume.docx` exists
- Check your `ANTHROPIC_API_KEY` is valid
- Look at `data/logs/agent.log` for specific errors
