# 🤖 LinkedIn Job Agent

An AI-powered autonomous agent that searches LinkedIn for relevant DevOps/Cloud/Automation jobs, tailors your resume to each JD, sends you an approval email before applying, and tracks everything in a structured log.

---

## 🗂️ Project Structure

```
job-agent/
├── agents/
│   ├── job_searcher.py        # LinkedIn job scraping agent
│   ├── resume_tailor.py       # AI-powered resume customization
│   ├── application_agent.py   # Applies to jobs after approval
│   └── orchestrator.py        # Master controller (runs all agents)
├── config/
│   ├── settings.yaml          # All configurable settings
│   └── keywords.yaml          # Job search keywords & locations
├── data/
│   ├── resumes/
│   │   ├── base_resume.docx   # Your master resume (place here)
│   │   └── tailored/          # Auto-generated tailored resumes
│   ├── jobs/
│   │   ├── found_jobs.json    # All discovered jobs
│   │   └── applied_jobs.json  # Jobs that were approved & applied
│   └── logs/
│       └── agent.log          # Full execution log
├── notifications/
│   └── email_notifier.py      # Email approval system
├── scripts/
│   ├── setup.sh               # One-time environment setup
│   └── run_agent.sh           # Quick run script
├── docs/
│   └── SETUP_GUIDE.md         # Detailed setup instructions
├── .github/
│   └── workflows/
│       └── daily_job_search.yml  # GitHub Actions for automation
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
└── README.md
```

---

## ⚡ Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/YOUR_USERNAME/job-agent.git
cd job-agent
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your credentials
nano .env
```

### 3. Add Your Resume
Place your base resume as `data/resumes/base_resume.docx`

### 4. Run the Agent
```bash
python agents/orchestrator.py
```

---

## 🔄 How It Works

```
[Scheduler / GitHub Actions]
        ↓
[Job Searcher Agent]          → Searches LinkedIn for DevOps/K8s/Python/Ansible jobs
        ↓
[Resume Tailor Agent]         → AI rewrites resume sections to match each JD
        ↓
[Email Notifier]              → Sends approval email to raulo.raj@gmail.com
        ↓
[User Approves via Email]     → Clicks APPROVE or SKIP link
        ↓
[Application Agent]           → Submits application on LinkedIn
        ↓
[Logger]                      → Saves everything to data/logs/
```

---

## 🔧 Configuration

Edit `config/settings.yaml` for:
- Job search keywords
- Target locations (UAE / Global)
- Experience level filters
- Email settings
- Application limits per run

---

## 📅 Automation (GitHub Actions)

The agent runs automatically via GitHub Actions:
- **Daily at 8:00 AM UAE time** — job search + apply approved jobs
- **Manual trigger** — run anytime from GitHub Actions tab

See `.github/workflows/daily_job_search.yml`

---

## ⚠️ Important Notes

- LinkedIn scraping may require a valid session cookie (`LI_AT` token)
- Use responsibly — LinkedIn has rate limits
- Never commit your `.env` file or `LI_AT` token to GitHub
- The approval email system ensures you stay in control

---

## 📄 License

MIT
